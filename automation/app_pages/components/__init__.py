"""Composable Playwright controls shared by desktop-app page objects."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Literal

from playwright.sync_api import Locator, Page, expect

CheckboxState = Literal["checked", "unchecked", "mixed"]


class OverflowMenu:
    """An overflow trigger and its menu, scoped to one card or row."""

    def __init__(self, scope: Locator, trigger: Locator, *, menu: Locator | None = None) -> None:
        self.scope = scope
        self.trigger = trigger
        self.menu = scope if menu is None else menu

    def open(self) -> None:
        expect(self.trigger).to_be_visible()
        expect(self.trigger).to_be_enabled()
        self.trigger.click()

    def item(self, *names: str, test_id: str | re.Pattern[str] | None = None) -> Locator:
        if test_id is not None:
            candidate = self.menu.get_by_test_id(test_id).first
            try:
                expect(candidate).to_be_visible(timeout=2_000)
                return candidate
            except AssertionError:
                pass
        for name in names:
            candidate = self.menu.get_by_role("button", name=name, exact=True).first
            try:
                expect(candidate).to_be_visible(timeout=2_000)
                return candidate
            except AssertionError:
                continue
        raise LookupError(f"Overflow item not found: {names or (test_id,)}")

    def has_item(self, name: str) -> bool:
        candidate = self.menu.get_by_role("button", name=name, exact=True)
        return candidate.count() > 0 and candidate.first.is_visible()

    def click_item(self, *names: str, test_id: str | re.Pattern[str] | None = None) -> None:
        item = self.item(*names, test_id=test_id)
        expect(item).to_be_visible()
        item.click()

    def close(self) -> None:
        self.scope.page.keyboard.press("Escape")


class Slideout:
    """A slideout with conventional field and confirmation test IDs."""

    def __init__(self, page: Page, name: str, *, serial: str | None = None) -> None:
        self.page = page
        self.name = name
        self.serial = serial

    def _test_id(self, suffix: str) -> str | re.Pattern[str]:
        if self.serial:
            return f"{self.name}Slideout_{suffix}_{self.serial}"
        return re.compile(rf"^{re.escape(self.name)}Slideout_{re.escape(suffix)}_")

    @property
    def field(self) -> Locator:
        return self.page.get_by_test_id(self._test_id("input_field")).first

    @property
    def confirm_button(self) -> Locator:
        return self.page.get_by_test_id(self._test_id("btn")).first

    def fill(self, value: str) -> None:
        NumericField(self.field).fill(value)

    def confirm(self) -> None:
        expect(self.confirm_button).to_be_enabled()
        self.confirm_button.click()

    def close(self) -> None:
        close = self.page.get_by_role("button", name="exit")
        if close.count() > 0 and close.first.is_visible():
            close.first.click()
        else:
            self.page.keyboard.press("Escape")


class ToggleSwitch:
    """A role=switch control whose state is exposed through aria-checked."""

    def __init__(self, page: Page, aria_label: str, *, scope: Locator | None = None) -> None:
        parent: Page | Locator = page if scope is None else scope
        self.locator = parent.get_by_role("switch", name=aria_label)

    def is_on(self) -> bool:
        return self.locator.get_attribute("aria-checked") == "true"

    def toggle(self) -> None:
        expect(self.locator).to_be_visible()
        self.locator.click()

    def turn_on(self) -> None:
        if not self.is_on():
            self.toggle()
        expect(self.locator).to_have_attribute("aria-checked", "true")

    def turn_off(self) -> None:
        if self.is_on():
            self.toggle()
        expect(self.locator).to_have_attribute("aria-checked", "false")


class RoundTabBar:
    """Round navigation tabs addressed by label and route slug."""

    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")

    def tab(self, label: str, slug: str) -> Locator:
        return self.page.locator(f'a[href*="{self.base_url}/{slug}"]').get_by_text(label, exact=True)

    def open(self, label: str, slug: str) -> None:
        tab = self.tab(label, slug)
        expect(tab).to_be_visible()
        tab.scroll_into_view_if_needed()
        tab.click()
        expect(self.page).to_have_url(re.compile(rf"{re.escape(self.base_url)}/{re.escape(slug)}"))
        expect(tab).to_have_attribute("aria-current", "page")


class BasicButton:
    """The app's ``basic_button_{label}`` control."""

    def __init__(self, scope: Page | Locator, label: str) -> None:
        self.locator = scope.get_by_test_id(f"basic_button_{label}")
        self.label = label

    def click(self) -> None:
        expect(self.locator).to_be_visible()
        expect(self.locator).to_be_enabled()
        self.locator.click()

    def is_visible(self) -> bool:
        return self.locator.count() > 0 and self.locator.first.is_visible()


class NumericField:
    """A numeric field represented by either an input or a wrapper."""

    def __init__(self, locator: Locator) -> None:
        self.locator = locator

    @property
    def input(self) -> Locator:
        nested = self.locator.locator("input")
        return nested.first if nested.count() > 0 else self.locator

    def fill(self, value: str, *, timeout: float = 10_000) -> None:
        expect(self.locator).to_be_visible(timeout=timeout)
        field = self.input
        field.scroll_into_view_if_needed()
        field.fill("", timeout=timeout)
        field.fill(value, timeout=timeout)
        field.press("Tab")


class StatusChip:
    """Semantic status chip with neutral/success/warning/error variants."""

    VARIANTS = ("neutral", "success", "warning", "error")

    def __init__(self, scope: Page | Locator) -> None:
        self.scope = scope

    @property
    def locator(self) -> Locator:
        pattern = re.compile(r"^Chip_(neutral|success|warning|error)$")
        return self.scope.get_by_test_id(pattern).first

    def read(self) -> tuple[str, str]:
        expect(self.locator).to_be_visible()
        test_id = self.locator.get_attribute("data-testid") or ""
        return test_id.removeprefix("Chip_"), self.locator.inner_text().strip()


class DeckInfoLabel:
    """A deck location, module, or state label."""

    def __init__(self, scope: Page | Locator, value: str) -> None:
        self.locator = scope.get_by_test_id(f"RobotInfoLabel_{value}")

    def text(self) -> str:
        expect(self.locator).to_be_visible()
        return self.locator.inner_text().strip()


class ListAccordion:
    """Shared expandable list row used by setup and run-record tables."""

    def __init__(self, root: Locator) -> None:
        self.root = root

    @property
    def toggle(self) -> Locator:
        return self.root.get_by_test_id("chevron-down").or_(self.root.get_by_test_id("chevron-up")).first

    def is_expanded(self) -> bool:
        return self.root.get_by_test_id("chevron-up").count() > 0

    def expand(self) -> None:
        if not self.is_expanded():
            self.toggle.click()

    def collapse(self) -> None:
        if self.is_expanded():
            self.toggle.click()

    def header_text(self) -> str:
        return self.root.inner_text().strip()


class RowCheckbox:
    """Tri-state CheckboxBasic, always resolved inside a caller-provided scope."""

    def __init__(self, scope: Locator) -> None:
        self.locator = scope.locator('input[type="checkbox"]').first

    def state(self) -> CheckboxState:
        value = self.locator.get_attribute("aria-checked")
        if value == "true":
            return "checked"
        if value == "mixed":
            return "mixed"
        return "unchecked"

    def check(self) -> None:
        if self.state() != "checked":
            self.locator.click()
        expect(self.locator).to_have_attribute("aria-checked", "true")

    def uncheck(self) -> None:
        if self.state() != "unchecked":
            self.locator.click()
        expect(self.locator).to_have_attribute("aria-checked", "false")


class Banner:
    """Inline app banner addressed by semantic variant."""

    def __init__(self, scope: Page | Locator, variant: str) -> None:
        self.locator = scope.get_by_test_id(f"Banner_{variant}")

    def text(self) -> str:
        expect(self.locator).to_be_visible()
        return self.locator.inner_text().strip()


def visible_texts(locators: Iterable[Locator]) -> list[str]:
    """Return stripped text for visible locators."""
    return [locator.inner_text().strip() for locator in locators if locator.is_visible()]


__all__ = [
    "Banner",
    "BasicButton",
    "CheckboxState",
    "DeckInfoLabel",
    "ListAccordion",
    "NumericField",
    "OverflowMenu",
    "RoundTabBar",
    "RowCheckbox",
    "Slideout",
    "StatusChip",
    "ToggleSwitch",
]

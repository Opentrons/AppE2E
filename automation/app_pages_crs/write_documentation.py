"""CRS audit note: record the Action list, type it, confirm.

Every Compliance Ready mutation that needs a reason uses the same screen:
read the Action list text that is on screen, type that text into the note,
click Confirm. The recorded lines are what later script asserts should match.
Callers then check that the action itself finished (lights flipped, deck
updated, module setpoint applied).
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Locator, Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from automation.app_helpers.test_progress import log_done, log_step, safe_print
from automation.app_pages_crs.documentation_required_page import AppDocumentationRequired

_PAGE_ATTR = "_crs_documented_actions"
_GUARD = threading.local()
_RECORD_PATH = Path(__file__).resolve().parents[2] / "artifacts" / "crs_documented_actions.log"


def _guarded() -> bool:
    return bool(getattr(_GUARD, "active", False))


@contextmanager
def _guard() -> Iterator[None]:
    """Keep Confirm clicks inside ``write`` from re-entering the click hook."""
    _GUARD.active = True
    try:
        yield
    finally:
        _GUARD.active = False


class WriteDocumentation:
    """Fill Documentation required from the Action list that is already showing."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.docs = AppDocumentationRequired(page)

    @classmethod
    def recorded_on(cls, page: Page) -> list[str]:
        """Action-list texts confirmed on this page since the last clear."""
        recorded = getattr(page, _PAGE_ATTR, None)
        return list(recorded) if recorded else []

    @classmethod
    def clear_recorded(cls, page: Page) -> None:
        setattr(page, _PAGE_ATTR, [])

    @staticmethod
    def _remember(page: Page, actions: list[str]) -> None:
        """Keep this test's actions and append each line for later script updates."""
        history = WriteDocumentation.recorded_on(page)
        history.extend(actions)
        setattr(page, _PAGE_ATTR, history)
        _RECORD_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _RECORD_PATH.open("a", encoding="utf-8") as record:
            for action in actions:
                safe_print(f"  [write_documentation] recorded action: {action}")
                record.write(f"{action}\n")

    def action_list_items(self) -> list[str]:
        """Visible rows under Action list, in order."""
        expect(self.docs.action_list_heading).to_be_visible()
        list_root = self.docs.action_list_heading.locator("xpath=following-sibling::*[1]")
        expect(list_root).to_be_visible()
        rows = list_root.locator("xpath=./div")
        texts: list[str] = []
        for index in range(rows.count()):
            text = " ".join(rows.nth(index).inner_text().split())
            if text and text not in texts:
                texts.append(text)
        if not texts:
            raise AssertionError("Documentation required Action list was empty")
        return texts

    def write(self) -> list[str]:
        """Record the Action list text on screen, type it into the note, and confirm.

        Returns the rows that were on the list. Those strings are also appended
        to ``artifacts/crs_documented_actions.log``.
        """
        expect(self.docs.heading).to_be_visible()
        actions = self.action_list_items()
        note = "\n".join(actions)
        log_step(f"Documentation required — Action list: {actions}")
        self.docs.note_field.fill(note)
        self.docs.confirm_button.click()
        expect(self.docs.heading).to_be_hidden(timeout=15_000)
        self._remember(self.page, actions)
        log_done(f"Confirmed documentation for: {actions}")
        return actions

    def complete_if_visible(self, *, timeout_ms: int = 1_000) -> list[str] | None:
        """Write documentation when the screen is up. Return None when it is not."""
        try:
            expect(self.docs.heading).to_be_visible(timeout=timeout_ms)
        except AssertionError:
            return None
        return self.write()


@contextmanager
def install_documentation_fallback(page: Page) -> Iterator[None]:
    """After a CRS click, confirm Documentation required when that screen appears.

    On click timeout, clear the screen if it is what blocked the click, then retry once.
    Clicks used to fill and confirm the note use the unwrapped Playwright click.
    """
    original_click = Locator.click

    def wrapped_click(locator: Locator, *args: object, **kwargs: object) -> None:
        if _guarded():
            return original_click(locator, *args, **kwargs)
        target = locator.page if hasattr(locator, "page") else page
        try:
            original_click(locator, *args, **kwargs)
        except PlaywrightTimeoutError as error:
            with _guard():
                actions = WriteDocumentation(target).complete_if_visible(timeout_ms=1_000)
            if not actions:
                raise error
            safe_print(f"  [write_documentation] cleared {actions}; retrying click")
            return original_click(locator, *args, **kwargs)
        with _guard():
            actions = WriteDocumentation(target).complete_if_visible(timeout_ms=1_000)
        if actions:
            safe_print(f"  [write_documentation] confirmed {actions}")

    Locator.click = wrapped_click  # type: ignore[method-assign]
    try:
        yield
    finally:
        Locator.click = original_click  # type: ignore[method-assign]

"""Page object for a robot's Deck Configuration tab."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

from automation.app_pages.base_app.app_base_page import AppBasePage
from automation.app_pages.base_app.devices_page import DevicesPage

# Labels rendered on configured DeckConfigurator buttons (not data-testids).
# Most module items do not set data-testid; Temperature is the exception (slot AA id).
CONFIGURED_MODULE_LABELS = (
    "Waste",
    "Temperature",
    "Heater-Shaker",
    "Thermocycler",
    "Absorbance",
    "Stacker",
    "Magnetic Block",
    "Trash",
)


class DeckConfigurationPage(AppBasePage):
    """Inspect and configure modules and fixtures on the Flex deck."""

    SLOT_IDS = ("B1", "C1", "D1", "B3", "D3")

    def __init__(self, page: Page, *, robot_name: str) -> None:
        super().__init__(page)
        self.robot_name = robot_name

    def open(self) -> None:
        devices = DevicesPage(self.page, robot_name=self.robot_name)
        devices.open_deck_configuration(use_tabs=True)
        expect(self.page).to_have_url(devices.robot_deck_configuration_url)

    def slot(self, slot_id: str) -> Locator:
        if slot_id not in self.SLOT_IDS:
            raise ValueError(f"Unsupported configurable slot: {slot_id}")
        return self.page.get_by_test_id(slot_id)

    def module_button(self, label: str) -> Locator:
        """Configured deck button by accessible name (e.g. ``Temperature``)."""
        return self.page.get_by_role("button", name=label, exact=True)

    def configured_module_labels(self) -> list[str]:
        """Return visible configured module/fixture labels (one entry per button)."""
        labels: list[str] = []
        for name in CONFIGURED_MODULE_LABELS:
            count = self.module_button(name).count()
            labels.extend([name] * count)
        return labels

    def _open_add_menu(self, slot_id: str) -> None:
        """Click an empty slot and wait for the Fixtures / Modules chooser modal."""
        self.slot(slot_id).click()
        expect(
            self.page.get_by_text(
                "Choose an item below to add to your deck configuration.",
                exact=False,
            )
        ).to_be_visible()

    def _select_add_category(self, category: str) -> None:
        """Click ``Select options`` for ``Fixtures`` or ``Modules`` (``data-testid``)."""
        if category not in ("Fixtures", "Modules"):
            raise ValueError(f"Unknown deck add category: {category}")
        button = self.page.get_by_test_id(category)
        expect(button).to_be_visible()
        button.click()

    def _click_add_option(self, option: str | re.Pattern[str]) -> None:
        """Click an Add row by option ``data-testid`` (USB port may vary)."""
        control = self.page.get_by_test_id(option)
        expect(control.first).to_be_visible()
        control.first.click()

    def add_module_to_slot(self, slot_id: str, display_name: str | re.Pattern[str]) -> None:
        """Add any module via empty slot → Modules → Select options → Add.

        Same chooser pattern for every module (Temperature, Magnetic Block, …).
        Option testids may include a USB port, e.g. ``Temperature Module GEN2 in USB-4``;
        pass a regex when the port is unknown.
        """
        self._open_add_menu(slot_id)
        self._select_add_category("Modules")
        self._click_add_option(display_name)

    def add_fixture_to_slot(self, slot_id: str, fixture: str | re.Pattern[str]) -> None:
        """Add any fixture via empty slot → Fixtures → Select options → Add."""
        self._open_add_menu(slot_id)
        self._select_add_category("Fixtures")
        self._click_add_option(fixture)
        # Some fixtures show a confirmation control with a title-cased testid.
        if isinstance(fixture, str):
            confirmation = self.page.get_by_test_id(fixture.title())
            if confirmation.count() > 0 and confirmation.first.is_visible():
                confirmation.first.click()

    def remove_module_by_label(self, label: str) -> None:
        """Click a configured module/fixture button to remove it (immediate, no confirm)."""
        button = self.module_button(label)
        before = button.count()
        expect(button.first).to_be_visible()
        button.first.click()
        expect(button).to_have_count(before - 1)

    def remove_from_slot(self, slot_id: str) -> None:
        """Remove the configured item whose ``data-testid`` ends with ``slot_id``.

        Only works for items that set a slot-suffixed testid (e.g. Temperature → ``D1``
        / ``temperatureModuleV2D1``). Prefer :meth:`remove_module_by_label` otherwise.
        """
        configured = self.page.get_by_test_id(re.compile(rf"(?:.*)?{re.escape(slot_id)}$"))
        # Prefer the non-empty configured control when both empty-slot and module match.
        expect(configured.first).to_be_visible()
        configured.first.click()

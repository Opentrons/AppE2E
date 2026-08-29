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

    def add_module_to_slot(self, slot_id: str, display_name: str | re.Pattern[str]) -> None:
        """Open an empty slot and add a module option by Add-button ``data-testid``.

        Option testids look like ``Temperature Module GEN2 in USB-4`` — pass a
        regex when the USB port is not known up front.
        """
        self.slot(slot_id).click()
        self.page.get_by_test_id("Modules").click()
        option = self.page.get_by_test_id(display_name)
        expect(option.first).to_be_visible()
        option.first.click()

    def add_fixture_to_slot(self, slot_id: str, fixture: str | re.Pattern[str]) -> None:
        self.slot(slot_id).click()
        self.page.get_by_test_id("Fixtures").click()
        option = self.page.get_by_test_id(fixture)
        expect(option.first).to_be_visible()
        option.first.click()
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

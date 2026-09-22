"""Page object for a robot's Deck Configuration tab."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

from automation.app_pages.base_app.app_base_page import AppBasePage
from automation.app_pages.base_app.devices_page import DevicesPage

# Accessible names on configured deck buttons (DeckConfigurator item labels).
CONFIGURED_MODULE_LABELS = (
    "Waste",
    "Temperature",
    "Heater-Shaker",
    "Thermocycler",
    "Absorbance",
    "Stacker",
    "Mag",  # MagneticBlockItem → deck_configuration.mag_block
    "Trash",
)

# FixtureOption data-testid values; USB/stacker ports vary by robot wiring.
TEMPERATURE_OPTION = re.compile(r"^Temperature Module GEN2")
HEATER_SHAKER_OPTION = re.compile(r"^Heater-Shaker Module GEN1")
THERMOCYCLER_OPTION = re.compile(r"^Thermocycler Module GEN2")
MAGNETIC_BLOCK_OPTION = "Magnetic Block GEN1"
ABSORBANCE_OPTION = re.compile(r"^Absorbance Plate Reader Module GEN1")
STACKER_OPTION = re.compile(r"^Flex Stacker Module GEN1")
WASTE_CHUTE_OPTION = "Waste chute"


class DeckConfigurationPage(AppBasePage):
    """Inspect and configure modules and fixtures on the Flex deck."""

    SLOT_IDS = ("A3", "B1", "B3", "C1", "D1", "D3", "fakeC4", "fakeD4")

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
        """Configured deck button by accessible name (e.g. ``Temperature``, ``Stacker``)."""
        return self.page.get_by_role("button", name=label, exact=True)

    def add_modal(self) -> Locator:
        return self.page.get_by_role("dialog", name="ModalShell_ModalArea")

    def configured_module_labels(self) -> list[str]:
        """Return visible configured module/fixture labels (one entry per button)."""
        labels: list[str] = []
        for name in CONFIGURED_MODULE_LABELS:
            count = self.module_button(name).count()
            labels.extend([name] * count)
        return labels

    def dismiss_open_add_modal(self) -> None:
        """Close a leftover Add-to-slot modal if one is open."""
        close = self.page.locator('[data-testid^="ModalHeader_icon_close_"]')
        if close.count() == 0 or not close.first.is_visible():
            return
        close.first.click()
        expect(self.add_modal()).to_be_hidden()

    def _open_add_menu(self, slot_id: str) -> None:
        """Click an empty slot and wait for the Fixtures / Modules chooser modal."""
        self.dismiss_open_add_modal()
        self.slot(slot_id).click()
        expect(self.add_modal()).to_be_visible()
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

    def _option_add_button(self, option: str | re.Pattern[str]) -> Locator:
        """Primary ``Add`` for a FixtureOption row.

        ``FixtureOption`` sets ``data-testid={optionName}`` on both Identify and Add
        when Identify is present. Intersect role=Add with the option testid so we
        never click Identify (``.first`` on the testid alone).
        """
        return self.page.get_by_role("button", name="Add", exact=True).and_(self.page.get_by_test_id(option))

    def _click_option_add(self, option: str | re.Pattern[str]) -> None:
        """Click the primary Add control for the given FixtureOption testid/pattern."""
        add = self._option_add_button(option)
        expect(add.first).to_be_visible()
        add.first.click()

    def _click_option_row(self, option: str | re.Pattern[str]) -> None:
        """Click a FixtureOption row control (Add when present, else the testid button).

        Use when the primary action is not labeled Add (e.g. Waste chute → Select options).
        """
        add = self._option_add_button(option)
        if add.count() > 0:
            expect(add.first).to_be_visible()
            add.first.click()
            return
        control = self.page.get_by_test_id(option)
        expect(control.first).to_be_visible()
        control.first.click()

    def add_module_to_slot(self, slot_id: str, display_name: str | re.Pattern[str]) -> None:
        """Add a module: empty slot → Modules → Add (USB port may vary)."""
        self._open_add_menu(slot_id)
        self._select_add_category("Modules")
        self._click_option_add(display_name)

    def add_fixture_to_slot(self, slot_id: str, fixture: str | re.Pattern[str]) -> None:
        """Add a fixture: empty slot → Fixtures → row action (+ title-case confirm)."""
        self._open_add_menu(slot_id)
        self._select_add_category("Fixtures")
        self._click_option_row(fixture)
        if isinstance(fixture, str):
            confirmation = self.page.get_by_test_id(fixture.title())
            if confirmation.count() > 0 and confirmation.first.is_visible():
                confirmation.first.click()

    def add_stacker_to_column(
        self,
        column_id: str,
        option: str | re.Pattern[str] = STACKER_OPTION,
    ) -> None:
        """Add a Flex Stacker on ``fakeC4`` / ``fakeD4`` via Modules → Add.

        Success = empty column control gone and one more ``Stacker`` deck button.
        """
        before = self.module_button("Stacker").count()
        self._open_add_menu(column_id)
        self._select_add_category("Modules")
        self._click_option_add(option)
        expect(self.slot(column_id)).to_have_count(0, timeout=15_000)
        expect(self.module_button("Stacker")).to_have_count(before + 1, timeout=15_000)

    def configure_standard_empty_deck(self) -> None:
        """Populate an empty Flex deck with the standard QA lab layout.

        - D1 Temperature Module GEN2
        - C1 Heater-Shaker Module GEN1
        - B1 Thermocycler Module GEN2
        - A3 Magnetic Block GEN1
        - B3 Absorbance Plate Reader Module GEN1
        - fakeC4 / fakeD4 Flex Stacker Module GEN1
        - D3 Waste chute
        """
        self.dismiss_open_add_modal()

        self.add_module_to_slot("D1", TEMPERATURE_OPTION)
        expect(self.page.get_by_test_id("temperatureModuleV2D1")).to_be_visible()

        self.add_module_to_slot("C1", HEATER_SHAKER_OPTION)
        expect(self.module_button("Heater-Shaker")).to_be_visible()

        self.add_module_to_slot("B1", THERMOCYCLER_OPTION)
        expect(self.module_button("Thermocycler")).to_be_visible()

        self.add_module_to_slot("A3", MAGNETIC_BLOCK_OPTION)
        expect(self.page.get_by_test_id("magneticBlockV1A3")).to_be_visible()

        self.add_module_to_slot("B3", ABSORBANCE_OPTION)
        expect(self.module_button("Absorbance")).to_be_visible()

        self.add_stacker_to_column("fakeC4")
        self.add_stacker_to_column("fakeD4")
        expect(self.module_button("Stacker")).to_have_count(2)

        self.add_fixture_to_slot("D3", WASTE_CHUTE_OPTION)
        expect(self.module_button("Waste")).to_be_visible()

    def remove_module_by_label(self, label: str) -> None:
        """Click a configured module/fixture button to remove it (immediate, no confirm)."""
        button = self.module_button(label)
        before = button.count()
        expect(button.first).to_be_visible()
        button.first.click()
        expect(button).to_have_count(before - 1)

    def remove_from_slot(self, slot_id: str) -> None:
        """Remove the configured item whose ``data-testid`` ends with ``slot_id``."""
        configured = self.page.get_by_test_id(re.compile(rf"(?:.*)?{re.escape(slot_id)}$"))
        expect(configured.first).to_be_visible()
        configured.first.click()

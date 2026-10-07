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
    "Stage",  # deck expansion / staging area on A4
    "Trash bin",
)

# FixtureOption data-testid values; USB/stacker ports vary by robot wiring.
TEMPERATURE_OPTION = re.compile(r"^Temperature Module GEN2")
HEATER_SHAKER_OPTION = re.compile(r"^Heater-Shaker Module GEN1")
THERMOCYCLER_OPTION = re.compile(r"^Thermocycler Module GEN2")
MAGNETIC_BLOCK_OPTION = "Magnetic Block GEN1"
ABSORBANCE_OPTION = re.compile(r"^Absorbance Plate Reader Module GEN1")
STACKER_OPTION = re.compile(r"^Flex Stacker Module GEN1")
STAGING_AREA_OPTION = "Staging Area Slot"
WASTE_CHUTE_OPTION = "Waste chute"

# Slot, add-modal option, and the label on the configured deck button.
_STANDARD_MODULES: tuple[tuple[str, str | re.Pattern[str], str], ...] = (
    ("D1", TEMPERATURE_OPTION, "Temperature"),
    ("C1", HEATER_SHAKER_OPTION, "Heater-Shaker"),
    ("B1", THERMOCYCLER_OPTION, "Thermocycler"),
    ("A3", MAGNETIC_BLOCK_OPTION, "Mag"),
    ("B3", ABSORBANCE_OPTION, "Absorbance"),
)

_STANDARD_LABELS = (
    "Temperature",
    "Heater-Shaker",
    "Thermocycler",
    "Mag",
    "Absorbance",
    "Stage",
    "Waste",
)


class DeckConfigurationPage(AppBasePage):
    """Inspect and configure modules and fixtures on the Flex deck."""

    SLOT_IDS = ("A3", "B1", "B3", "C1", "D1", "D3", "fakeA4", "fakeC4", "fakeD4")

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

    # Modules that Module Wizard calibration exercises (HS / TD / TC).
    CALIBRATION_MODULE_LABELS = ("Temperature", "Heater-Shaker", "Thermocycler")

    def ensure_calibration_modules_configured(self) -> list[str]:
        """Open Deck Configuration and ensure HS / Temp / TC slots are set.

        Factory-default trash on A3 (or a fully empty deck) is filled with the
        standard QA lab layout. A deck that already has other fixtures/modules but
        is still missing a calibration module raises with the current labels.
        Returns the configured labels after the check.
        """
        self.open()
        labels = self.configured_module_labels()
        present = set(labels)
        missing = [name for name in self.CALIBRATION_MODULE_LABELS if name not in present]

        if not missing:
            return labels

        # Trash bin alone is the Flex factory default — treat it like an empty deck.
        meaningful = [label for label in labels if label != "Trash bin"]
        if meaningful:
            raise AssertionError(
                "Deck is configured but missing modules required for calibration: "
                f"{missing}. Current labels: {labels}"
            )

        self.configure_standard_deck()
        after = self.configured_module_labels()
        still_missing = [name for name in self.CALIBRATION_MODULE_LABELS if name not in set(after)]
        if still_missing:
            raise AssertionError(
                "Standard deck setup did not place calibration modules: "
                f"{still_missing}. Labels after setup: {after}"
            )
        return after

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
        if not self._slot_is_empty(slot_id):
            raise AssertionError(f"Slot {slot_id} is not empty, so a module cannot be added")
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

    def configure_standard_deck(self) -> list[str]:
        """Add any missing pieces of the standard QA lab layout.

        Temperature on D1, Heater-Shaker on C1, Thermocycler on B1, Magnetic Block on A3,
        Absorbance Reader on B3, Flex Stackers on columns C and D, deck expansion on A4,
        and a waste chute on D3.
        A module that is already on the deck is left in place. Factory-default trash on A3
        is cleared before Mag is added. Returns the labels that were added.
        """
        self.dismiss_open_add_modal()
        added: list[str] = []

        for slot_id, option, label in _STANDARD_MODULES:
            if self._label_visible(label):
                continue
            self._clear_slot(slot_id)
            self.add_module_to_slot(slot_id, option)
            expect(self.module_button(label).first).to_be_visible(timeout=15_000)
            added.append(label)

        for column_id in ("fakeC4", "fakeD4"):
            if self.module_button("Stacker").count() >= 2:
                break
            if not self._slot_is_empty(column_id):
                continue
            before = self.module_button("Stacker").count()
            self.add_stacker_to_column(column_id)
            expect(self.module_button("Stacker")).to_have_count(before + 1, timeout=15_000)
            added.append(f"Stacker {column_id}")

        staging = self.ensure_staging_area_a4()
        if staging == "added":
            added.append("Stage")

        if not self._label_visible("Waste"):
            if not self._slot_is_empty("D3"):
                raise AssertionError("Slot D3 is not empty, so a waste chute cannot be added")
            self.add_fixture_to_slot("D3", WASTE_CHUTE_OPTION)
            expect(self.module_button("Waste").first).to_be_visible(timeout=15_000)
            added.append("Waste")

        self.expect_standard_layout()
        return added

    def ensure_staging_area_a4(self) -> str:
        """Add the deck expansion slot (staging area) on A4.

        Returns ``added`` or ``already present``.
        """
        if self._label_visible("Stage"):
            return "already present"
        if not self._slot_is_empty("fakeA4"):
            raise AssertionError("A4 is not empty, so a deck expansion slot cannot be added")
        self.add_fixture_to_slot("fakeA4", STAGING_AREA_OPTION)
        expect(self.module_button("Stage").first).to_be_visible(timeout=15_000)
        return "added"

    def configure_standard_empty_deck(self) -> list[str]:
        """Alias for :meth:`configure_standard_deck` (works on empty or trash-default decks)."""
        return self.configure_standard_deck()

    def expect_standard_layout(self) -> None:
        """Assert the standard QA lab modules and the waste chute are on the deck."""
        for label in _STANDARD_LABELS:
            expect(self.module_button(label).first).to_be_visible(timeout=10_000)
        expect(self.module_button("Stacker")).to_have_count(2, timeout=10_000)
        expect(self.module_button("Trash bin")).to_have_count(0)

    def _label_visible(self, label: str) -> bool:
        button = self.module_button(label)
        return button.count() > 0 and button.first.is_visible()

    def _slot_is_empty(self, slot_id: str) -> bool:
        slot = self.slot(slot_id)
        return slot.count() > 0 and slot.first.is_visible()

    def _clear_slot(self, slot_id: str) -> None:
        """Remove a fixture that is occupying ``slot_id`` instead of the standard module.

        A3 on Flex defaults to a trash bin. The standard layout uses a magnetic block there.
        """
        if self._slot_is_empty(slot_id):
            return
        if slot_id == "A3" and self._label_visible("Trash bin"):
            self.remove_module_by_label("Trash bin")
            expect(self.slot("A3")).to_be_visible(timeout=15_000)
            return
        raise AssertionError(f"Slot {slot_id} is not empty, so a module cannot be added")

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

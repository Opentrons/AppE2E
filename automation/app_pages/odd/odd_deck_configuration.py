"""Flex ODD deck configuration for the standard QA lab layout."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

from automation.app_pages.odd.odd_shell import OddShell

# Option names on the Add modal. USB modules include a port suffix, so match the prefix.
_TEMPERATURE = re.compile(r"^Temperature Module GEN2")
_HEATER_SHAKER = re.compile(r"^Heater-Shaker Module GEN1")
_THERMOCYCLER = re.compile(r"^Thermocycler Module GEN2")
_MAGNETIC_BLOCK = "Magnetic Block GEN1"
_ABSORBANCE = re.compile(r"^Absorbance Plate Reader Module GEN1")
_STACKER = re.compile(r"^Flex Stacker Module GEN1")

# Slot, add-modal option, and the label on the configured deck button.
_STANDARD_MODULES: tuple[tuple[str, str | re.Pattern[str], str], ...] = (
    ("D1", _TEMPERATURE, "Temperature"),
    ("C1", _HEATER_SHAKER, "Heater-Shaker"),
    ("B1", _THERMOCYCLER, "Thermocycler"),
    ("A3", _MAGNETIC_BLOCK, "Mag"),
    ("B3", _ABSORBANCE, "Absorbance"),
)


class OddDeckConfigurationPage(OddShell):
    """Deck configuration opened from the ODD overflow menu."""

    WASTE_CHUTE_OPTION = "Waste Chute"
    CHOOSER_TEXT = "Choose an item below to add to your deck configuration."

    def __init__(self, page: Page) -> None:
        """Bind the Playwright page for the remote ODD window."""
        super().__init__(page)

    def open(self) -> None:
        """Open Deck configuration from the overflow menu.

        The deck screen hides the top nav, so a session that is already there stays put.
        """
        self.dismiss_welcome_modal_if_present()
        if self.DECK_CONFIGURATION_URL.search(self.page.url):
            expect(self.page.get_by_text("Deck configuration", exact=True)).to_be_visible(timeout=15_000)
            return
        self.press(self.kebab_nav)
        deck = self.page.get_by_role("button", name="Deck configuration")
        expect(deck).to_be_visible(timeout=10_000)
        self.press(deck)
        expect(self.page).to_have_url(self.DECK_CONFIGURATION_URL, timeout=15_000)
        expect(self.page.get_by_text("Deck configuration", exact=True)).to_be_visible(timeout=15_000)

    def waste_chute(self) -> Locator:
        """Configured waste-chute button on the deck map."""
        return self.page.get_by_role("button", name="Waste", exact=True)

    def empty_slot(self, slot_id: str) -> Locator:
        """Empty configurable slot, addressed by its addressable-area id (for example ``D3``)."""
        return self.page.get_by_test_id(slot_id)

    def module_button(self, label: str) -> Locator:
        """Configured deck button by its short label (for example ``Temperature`` or ``Stacker``)."""
        return self.page.get_by_role("button", name=label, exact=True)

    def configure_standard_deck(self) -> list[str]:
        """Add any missing pieces of the standard QA lab layout.

        Temperature on D1, Heater-Shaker on C1, Thermocycler on B1, Magnetic Block on A3,
        Absorbance Reader on B3, a deck expansion slot on A4, Flex Stackers on columns C and D,
        and a waste chute on D3.
        A module that is already on the deck is left in place. Returns the labels that were added.
        """
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
            self.add_module_to_slot(column_id, _STACKER)
            expect(self.module_button("Stacker")).to_have_count(before + 1, timeout=15_000)
            added.append(f"Stacker {column_id}")

        staging = self.ensure_staging_area_a4()
        if staging == "added":
            added.append("Stage A4")

        waste = self.ensure_waste_chute()
        added.append(f"Waste chute {waste}")
        self.expect_standard_layout()
        return added

    def expect_standard_layout(self) -> None:
        """Assert the standard QA lab modules and the waste chute are on the deck."""
        for label in ("Temperature", "Heater-Shaker", "Thermocycler", "Mag", "Absorbance", "Stage", "Waste"):
            expect(self.module_button(label).first).to_be_visible(timeout=10_000)
        expect(self.module_button("Stacker")).to_have_count(2, timeout=10_000)

    def add_module_to_slot(self, slot_id: str, option: str | re.Pattern[str]) -> None:
        """Add a module: empty slot, Modules, then Add. The USB port in the option name may vary."""
        if not self._slot_is_empty(slot_id):
            raise AssertionError(f"Slot {slot_id} is not empty, so a module cannot be added")
        self.press(self.empty_slot(slot_id))
        chooser = self._chooser()
        expect(chooser).to_be_visible(timeout=10_000)
        modules = self.page.get_by_test_id("Modules")
        if modules.count() > 0 and modules.first.is_visible():
            self.press(modules.first)
        add = self.page.get_by_role("button", name="Add", exact=True).and_(self.page.get_by_test_id(option))
        expect(add.first).to_be_visible(timeout=15_000)
        self.press(add.first)
        expect(chooser).to_be_hidden(timeout=15_000)

    def _chooser(self) -> Locator:
        return self.page.get_by_text(self.CHOOSER_TEXT, exact=False)

    def _label_visible(self, label: str) -> bool:
        button = self.module_button(label)
        return button.count() > 0 and button.first.is_visible()

    def _clear_slot(self, slot_id: str) -> None:
        """Remove a fixture that is occupying ``slot_id`` instead of the standard module.

        A3 on this robot is often a trash bin. The standard layout uses a magnetic block there.
        """
        if self._slot_is_empty(slot_id):
            return
        if slot_id == "A3" and self._label_visible("Trash bin"):
            self.press(self.module_button("Trash bin").first)
            expect(self.empty_slot("A3")).to_be_visible(timeout=15_000)
            return
        raise AssertionError(f"Slot {slot_id} is not empty, so a module cannot be added")

    def _slot_is_empty(self, slot_id: str) -> bool:
        slot = self.empty_slot(slot_id)
        return slot.count() > 0 and slot.first.is_visible()

    def ensure_staging_area_a4(self) -> str:
        """Add the deck expansion slot (staging area) on A4.

        Returns ``added`` or ``already present``.
        """
        if self._label_visible("Stage"):
            return "already present"
        if not self._slot_is_empty("fakeA4"):
            raise AssertionError("A4 is not empty, so a deck expansion slot cannot be added")
        self.press(self.empty_slot("fakeA4"))
        chooser = self._chooser()
        expect(chooser).to_be_visible(timeout=10_000)
        fixtures = self.page.get_by_test_id("Fixtures")
        if fixtures.count() > 0 and fixtures.first.is_visible():
            self.press(fixtures.first)
        add = self.page.get_by_role("button", name="Add", exact=True).and_(
            self.page.get_by_test_id("Staging Area Slot")
        )
        expect(add).to_be_visible(timeout=10_000)
        self.press(add)
        expect(self.module_button("Stage").first).to_be_visible(timeout=15_000)
        expect(chooser).to_be_hidden(timeout=10_000)
        return "added"

    def ensure_waste_chute(self) -> str:
        """Add a waste chute on D3.

        If one is already configured, remove it first so this call performs the add.
        Returns ``replaced`` when an existing chute was removed, otherwise ``added``.
        """
        replaced = self.waste_chute().count() > 0 and self.waste_chute().first.is_visible()
        if replaced:
            self.remove_waste_chute()
        elif self.empty_slot("D3").count() == 0 or not self.empty_slot("D3").first.is_visible():
            raise AssertionError("Slot D3 is not empty, so a waste chute cannot be added")
        self.add_waste_chute()
        return "replaced" if replaced else "added"

    def remove_waste_chute(self) -> None:
        """Remove the configured waste chute. Removal is immediate."""
        waste = self.waste_chute()
        expect(waste).to_be_visible(timeout=10_000)
        self.press(waste)
        expect(waste).to_be_hidden(timeout=15_000)
        expect(self.empty_slot("D3")).to_be_visible(timeout=15_000)

    def add_waste_chute(self) -> None:
        """Add the uncovered waste chute to empty slot D3."""
        self.press(self.empty_slot("D3"))
        chooser = self._chooser()
        expect(chooser).to_be_visible(timeout=10_000)
        self.press(self.page.get_by_test_id("Fixtures"))
        self.press(self.page.get_by_test_id("Waste chute"))
        add = self.page.get_by_role("button", name="Add", exact=True).and_(
            self.page.get_by_test_id(self.WASTE_CHUTE_OPTION)
        )
        expect(add).to_be_visible(timeout=10_000)
        self.press(add)
        expect(self.waste_chute()).to_be_visible(timeout=15_000)
        expect(chooser).to_be_hidden(timeout=10_000)

    def save(self) -> None:
        """Press Save and leave Deck configuration."""
        save = self.page.get_by_role("button", name="Save", exact=True)
        expect(save).to_be_visible(timeout=10_000)
        self.press(save)
        expect(self.page).not_to_have_url(self.DECK_CONFIGURATION_URL, timeout=15_000)

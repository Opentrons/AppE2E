"""Page object for the five protocol run setup steps."""

from __future__ import annotations

from playwright.sync_api import Locator, Page, expect

from automation.app_pages.base_app.app_base_page import AppBasePage
from automation.app_pages.components import StatusChip, ToggleSwitch


class RunSetupPage(AppBasePage):
    """Interact with Instruments, Deck Hardware, offsets, labware, and camera setup."""

    STEPS = ("Instruments", "Deck Hardware", "Labware Offsets", "Labware & Liquids", "Camera")

    def __init__(self, page: Page) -> None:
        super().__init__(page)

    def step(self, title: str) -> Locator:
        if title not in self.STEPS:
            raise ValueError(f"Unknown run setup step: {title}")
        heading = self.page.get_by_text(title, exact=True).first
        return heading.locator(
            "xpath=ancestor::*[.//*[@data-testid='SetupStep_content_expanded' "
            "or @data-testid='SetupStep_content_collapsed']][1]"
        )

    def expand(self, title: str) -> Locator:
        root = self.step(title)
        expanded = root.get_by_test_id("SetupStep_content_expanded")
        if expanded.count() == 0 or not expanded.is_visible():
            root.get_by_text(title, exact=True).first.click()
        expect(root.get_by_test_id("SetupStep_content_expanded")).to_be_visible()
        return root

    def status(self, title: str) -> str:
        root = self.step(title)
        known = (
            "Action needed",
            "Offsets missing",
            "Check locations and volumes",
            "Check preferences",
        )
        for value in known:
            locator = root.get_by_text(value, exact=True)
            if locator.count() > 0:
                return value
        return ""

    def select_deck_list_view(self) -> None:
        self.expand("Deck Hardware").get_by_test_id("toggleGroup_leftButton").click()

    def select_deck_map_view(self) -> None:
        self.expand("Deck Hardware").get_by_test_id("toggleGroup_rightButton").click()

    def proceed_to_deck_hardware(self) -> None:
        self.expand("Instruments").get_by_role("button", name="Proceed to deck hardware").click()

    def proceed_to_labware_offsets(self) -> None:
        self.expand("Deck Hardware").get_by_role("button", name="Proceed to labware offsets").click()

    def apply_offsets(self) -> None:
        self.expand("Labware Offsets").get_by_role("button", name="Apply offsets").click()

    def confirm_placements(self) -> None:
        self.expand("Labware & Liquids").get_by_role("button", name="Confirm placements").click()

    def camera_status(self) -> tuple[str, str]:
        return StatusChip(self.expand("Camera")).read()

    def set_camera_enabled(self, enabled: bool) -> None:
        switch = ToggleSwitch(self.page, "Camera Status", scope=self.expand("Camera"))
        switch.turn_on() if enabled else switch.turn_off()

    def confirm_camera_preferences(self) -> None:
        self.expand("Camera").get_by_role("button", name="Confirm preferences").click()

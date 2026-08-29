"""Page object for the Devices list and robot detail navigation."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

from automation.app_helpers.app_readiness import dismiss_blocking_ui
from automation.app_helpers.left_nav import link, navigate_to
from automation.app_helpers.list_scroll import scroll_until_visible
from automation.app_helpers.locator_helpers import first_resolved
from automation.app_pages.base_app.app_base_page import AppBasePage
from automation.app_pages.components import OverflowMenu


class DevicesPage(AppBasePage):
    """Navigate from Devices landing to a robot detail page."""

    # Electron serves the SPA from file://…/index.html with hash routing (#/devices/…).
    DEVICES_LANDING_URL = re.compile(r"#/devices/?$")

    TAB_HARDWARE = "Hardware"
    TAB_DECK_CONFIGURATION = "Deck Configuration"
    TAB_RUN_HISTORY = "Run History"
    DEVICE_DETAILS_TAB_NAMES = (TAB_HARDWARE, TAB_DECK_CONFIGURATION, TAB_RUN_HISTORY)

    def __init__(self, page: Page, *, robot_name: str = "QA1Potato") -> None:
        """Bind the page and target robot display name."""
        super().__init__(page)
        self.robot_name = robot_name

    @property
    def nav_link(self) -> Locator:
        """Left-nav Devices link."""
        return link(self.page, "Devices")

    @property
    def robot_detail_url(self) -> re.Pattern[str]:
        """Hash route for this robot's detail page (any Device Details tab)."""
        return re.compile(
            rf"#/devices/{re.escape(self.robot_name)}"
            rf"(?:/(?:deck-configuration|run-history))?/?$"
        )

    @property
    def robot_hardware_url(self) -> re.Pattern[str]:
        """Hash route for the Hardware tab (default Device Details)."""
        return re.compile(rf"#/devices/{re.escape(self.robot_name)}/?$")

    @property
    def robot_deck_configuration_url(self) -> re.Pattern[str]:
        """Hash route for the Deck Configuration tab."""
        return re.compile(rf"#/devices/{re.escape(self.robot_name)}/deck-configuration/?$")

    @property
    def robot_run_history_url(self) -> re.Pattern[str]:
        """Hash route for the Run History tab."""
        return re.compile(rf"#/devices/{re.escape(self.robot_name)}/run-history/?$")

    def on_robot_detail(self) -> bool:
        """Return True when the current URL is this robot's Device Details page."""
        return self.robot_detail_url.search(self.page.url) is not None

    def device_details_tab(self, name: str) -> Locator:
        """RoundTab / RoundNavLink for a Device Details section by visible name."""
        return self.page.get_by_role("link", name=name, exact=True)

    def expect_device_details_tabs_visible(self) -> None:
        """Assert Hardware / Deck Configuration / Run History tabs are visible."""
        for name in self.DEVICE_DETAILS_TAB_NAMES:
            expect(self.device_details_tab(name)).to_be_visible()

    def expect_device_details_tabs_hidden(self) -> None:
        """Assert Device Details RoundTabs are not present (pre-tab layout)."""
        for name in self.DEVICE_DETAILS_TAB_NAMES:
            expect(self.device_details_tab(name)).to_have_count(0)

    def robot_card(self) -> Locator:
        """Best-effort robot card click target for ``robot_name``."""
        escaped_name = re.escape(self.robot_name)
        overflow_test_id = f"RobotCard_{self.robot_name}_overflowMenu"

        def _by_image_id() -> Locator:
            # Legacy: removed in app 4.0 (#21954).
            return self.page.locator(f"#RobotCard_{self.robot_name}_robotImage")

        def _by_overflow_card() -> Locator:
            return self.page.get_by_test_id(overflow_test_id).locator(
                f"xpath=ancestor::*[.//*[normalize-space()={self.robot_name!r}]][1]"
            )

        def _by_robot_name_in_card() -> Locator:
            return self.page.get_by_text(self.robot_name, exact=True).locator(
                f"xpath=ancestor::*[.//*[@data-testid={overflow_test_id!r}]][1]"
            )

        def _by_robot_name() -> Locator:
            return self.page.get_by_text(self.robot_name, exact=True)

        def _by_detail_link() -> Locator:
            return self.page.locator(f'a[href="#/devices/{escaped_name}"], a[href="/devices/{escaped_name}"]').filter(
                has_not=self.page.locator('[class*="crumb_link"]')
            )

        return first_resolved(
            (
                _by_image_id,
                _by_overflow_card,
                _by_robot_name_in_card,
                _by_robot_name,
                _by_detail_link,
            )
        )

    def navigate(self) -> None:
        """Open Devices, select the robot card, and wait for robot detail."""
        dismiss_blocking_ui(self.page)

        if self.on_robot_detail():
            return

        if not self.DEVICES_LANDING_URL.search(self.page.url):
            navigate_to(self.page, "Devices", self.DEVICES_LANDING_URL)

        card = scroll_until_visible(self.page, self.robot_card())
        card.click()
        expect(self.page).to_have_url(self.robot_detail_url)

    def _ensure_on_robot_detail(self) -> None:
        """Navigate to this robot's detail page when not already there."""
        dismiss_blocking_ui(self.page)
        if not self.on_robot_detail():
            self.navigate()

    def _click_device_details_tab(self, name: str, url: re.Pattern[str]) -> None:
        """Click a Device Details RoundTab and wait for its hash route."""
        tab = self.device_details_tab(name)
        expect(tab).to_be_visible()
        tab.click()
        expect(self.page).to_have_url(url)

    def open_hardware(self, *, use_tabs: bool) -> None:
        """Open Hardware (instruments/modules). With tabs, click the Hardware tab."""
        self._ensure_on_robot_detail()
        if use_tabs:
            self._click_device_details_tab(self.TAB_HARDWARE, self.robot_hardware_url)
            return
        # Legacy layout: instruments/modules are on the default detail scroll.
        expect(self.page).to_have_url(self.robot_hardware_url)

    def open_deck_configuration(self, *, use_tabs: bool) -> None:
        """Open Deck Configuration via tab (new) or scroll (legacy ≤9.1.2)."""
        self._ensure_on_robot_detail()
        if use_tabs:
            self._click_device_details_tab(self.TAB_DECK_CONFIGURATION, self.robot_deck_configuration_url)
            return

        heading = self.page.get_by_text(
            re.compile(rf"{re.escape(self.robot_name)}\s+Deck Configuration"),
            exact=False,
        )
        expect(heading.first).to_be_visible()
        heading.first.scroll_into_view_if_needed()

    def open_run_history(self, *, use_tabs: bool) -> None:
        """Open Run History via tab (new) or ``#recent-protocol-runs`` (legacy)."""
        self._ensure_on_robot_detail()
        if use_tabs:
            self._click_device_details_tab(self.TAB_RUN_HISTORY, self.robot_run_history_url)
            return

        section = self.page.locator("#recent-protocol-runs")
        expect(section).to_be_visible()
        section.scroll_into_view_if_needed()

    def overflow_button(self) -> Locator:
        """Robot Overview overflow (⋯) button — not the menu container."""
        return self.page.get_by_test_id("RobotOverview_overflowMenu").get_by_role("button", name="overflow")

    def overview_menu(self) -> OverflowMenu:
        """Return the robot-overview overflow component."""
        scope = self.page.get_by_test_id("RobotOverview_overflowMenu")
        return OverflowMenu(scope, self.overflow_button())

    def open_overflow_menu(self) -> None:
        """Open the Robot Overview overflow menu via the ⋯ button."""
        dismiss_blocking_ui(self.page)
        if not self.on_robot_detail():
            self.navigate()
        self.overview_menu().open()

    def home_gantry(self) -> None:
        """Home gantry from Robot Overview overflow: Home gantry."""
        self.open_overflow_menu()
        self.overview_menu().click_item(
            "Home gantry",
            test_id=f"RobotOverviewOverflowMenu_homeGantry_{self.robot_name}",
        )
        dismiss_blocking_ui(self.page)

    def open_robot_settings(self) -> None:
        """Open Robot Settings from Robot Overview overflow."""
        self.open_overflow_menu()
        self.overview_menu().click_item(
            "Robot Settings",
            test_id=f"RobotOverviewOverflowMenu_robotSettings_{self.robot_name}",
        )

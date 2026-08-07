"""Page object for the App Settings gear menu."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

from automation.app_helpers.app_readiness import (
    GEAR_NAV_DEBOUNCE_MS,
    click_when_ui_ready,
    dismiss_blocking_ui,
)
from automation.app_helpers.page_helpers import require_helper
from automation.app_helpers.screenshot_helper import ScreenshotHelper
from automation.app_pages.base_app.app_base_page import AppBasePage


class AppSettingsPage(AppBasePage):
    """App Settings gear menu — General, Privacy, Advanced, and optional Feature Flags."""

    CONNECT_IP_HEADING = "Connect to a Robot via IP Address"
    PRIVACY_HEADING = "Share App Analytics with Opentrons"
    PRIVACY_DESCRIPTION = (
        "Help Opentrons improve its products and services by automatically "
        "sending anonymous diagnostics and usage data."
    )
    SOFTWARE_UPDATE_HEADING = "Software Update"
    UPDATE_ALERT_COPY = re.compile(r"Receive an alert when .+ software update is available\.")
    ADVANCED_HEADING = "Update Channel"
    CUSTOM_LABWARE_HEADING = "Additional Custom Labware Source Folder"
    PREVENT_ROBOT_CACHING = "Prevent Robot Caching"
    CLEAR_UNAVAILABLE_ROBOTS = "Clear Unavailable Robots"
    CLEAR_ROBOTS_BUTTON = "Clear unavailable robots list"
    DEVELOPER_TOOLS = "Developer Tools"
    FEATURE_FLAGS_TAB = "Feature Flags"
    SETUP_CONNECTION = "Set up connection"
    ADD_IP_HOSTNAME = "Add IP Address or Hostname"

    TABS = (
        ("General", "general"),
        ("Privacy", "privacy"),
        ("Advanced", "advanced"),
        (FEATURE_FLAGS_TAB, "feature-flags"),
    )

    def __init__(self, page: Page, shots: ScreenshotHelper | None = None) -> None:
        """Bind the Playwright page and optional screenshot helper."""
        super().__init__(page)
        self.shots = shots

    @property
    def nav_link(self) -> Locator:
        """Navbar gear icon that opens App Settings."""
        return self.page.get_by_test_id("Navbar_settingsLink")

    def tab_link(self, name: str) -> Locator:
        """Return the sidebar link for an App Settings tab by visible name."""
        return self.page.locator('a[href*="/app-settings/"]').get_by_text(name, exact=True)

    def navigate(self) -> None:
        """Open App Settings from the navbar."""
        click_when_ui_ready(self.page, self.nav_link)
        expect(self.page).to_have_url(re.compile(r"#/app-settings"))
        self.page.wait_for_timeout(GEAR_NAV_DEBOUNCE_MS)

    def _open_tab(self, name: str, slug: str) -> bool:
        """Click a settings tab and wait for its hash URL slug to become active."""
        tab = self.tab_link(name)
        if tab.count() == 0:
            return False
        tab.scroll_into_view_if_needed()
        tab.click()
        # Electron uses file://…#/app-settings/<slug> — same hash lesson as Devices/Labware.
        self.page.wait_for_url(re.compile(rf"#/app-settings/{re.escape(slug)}/?$"))
        expect(tab).to_have_class(re.compile("active"))
        return True

    def _close_connect_ip_slideout(self) -> None:
        """Dismiss the Connect via IP slideout (Slideout_* test ids were removed)."""
        add_ip = self.page.get_by_text(self.ADD_IP_HOSTNAME, exact=True)
        done = self.page.get_by_role("button", name="Done", exact=True)
        if done.count() > 0 and done.is_visible():
            done.click()
        else:
            self.page.keyboard.press("Escape")
        expect(add_ip).to_be_hidden()

    def validate_general(self) -> None:
        """Validate General tab: connect via IP, software version, and update alerts."""
        expect(self.page.get_by_text("App Software Version", exact=True)).to_be_visible()
        update_button = self.page.get_by_role("button", name="View software update", exact=True)
        up_to_date = self.page.get_by_text("Up to date", exact=True)
        expect(update_button.or_(up_to_date)).to_be_visible()

        expect(self.page.get_by_text(self.SOFTWARE_UPDATE_HEADING, exact=True)).to_be_visible()
        expect(self.page.get_by_text(self.UPDATE_ALERT_COPY)).to_be_visible()
        expect(self.page.get_by_role("switch", name="Enable app update notifications")).to_be_visible()

        setup_connection = self.page.get_by_role("button", name=self.SETUP_CONNECTION, exact=True)
        setup_connection.scroll_into_view_if_needed()
        setup_connection.click()
        add_ip = self.page.get_by_text(self.ADD_IP_HOSTNAME, exact=True)
        try:
            expect(add_ip).to_be_visible()
        finally:
            self._close_connect_ip_slideout()
        dismiss_blocking_ui(self.page)

    def validate_privacy(self) -> None:
        """Open Privacy and assert the app analytics heading, copy, and toggle."""
        self._open_tab("Privacy", "privacy")
        expect(self.page.get_by_text(self.PRIVACY_HEADING, exact=True)).to_be_visible()
        expect(self.page.get_by_text(self.PRIVACY_DESCRIPTION, exact=True)).to_be_visible()
        expect(self.page.get_by_role("switch", name="analytics_opt_in")).to_be_visible()

    def validate_advanced(self) -> None:
        """Open Advanced and validate every settings section."""
        self._open_tab("Advanced", "advanced")
        expect(self.page.get_by_text(self.ADVANCED_HEADING, exact=True)).to_be_visible()
        expect(self.page.get_by_text(self.CUSTOM_LABWARE_HEADING, exact=True)).to_be_visible()
        change_folder = self.page.get_by_role("button", name="Change labware source folder", exact=True)
        add_folder = self.page.get_by_role("button", name="Add labware source folder", exact=True)
        expect(change_folder.or_(add_folder)).to_be_visible()
        expect(self.page.get_by_text(self.PREVENT_ROBOT_CACHING, exact=True)).to_be_visible()
        expect(self.page.get_by_role("switch", name="disable_robot_cache")).to_be_visible()
        expect(self.page.get_by_text(self.CLEAR_UNAVAILABLE_ROBOTS, exact=True)).to_be_visible()
        expect(self.page.get_by_role("button", name=self.CLEAR_ROBOTS_BUTTON, exact=True)).to_be_visible()
        expect(self.page.get_by_text(self.DEVELOPER_TOOLS, exact=True)).to_be_visible()
        expect(self.page.get_by_role("switch", name="enable_dev_tools")).to_be_visible()

    def validate_feature_flags(self) -> None:
        """Open Feature Flags when present and assert the tab heading is visible."""
        if not self._open_tab(self.FEATURE_FLAGS_TAB, "feature-flags"):
            return
        expect(self.page.get_by_text(self.FEATURE_FLAGS_TAB, exact=True)).to_be_visible()

    def validate_all_tabs(self) -> None:
        """Navigate to App Settings and validate every available tab."""
        self.navigate()
        self.validate_general()
        self.validate_privacy()
        self.validate_advanced()
        self.validate_feature_flags()

    def capture_all_tabs(self) -> None:
        """Validate each App Settings tab and save a screenshot per tab."""
        shots = require_helper(self.shots, "ScreenshotHelper", owner="AppSettingsPage", method="capture_all_tabs")

        self.navigate()
        self.validate_general()
        shots.capture("app_settings", "general")

        self.validate_privacy()
        shots.capture("app_settings", "privacy")

        self.validate_advanced()
        shots.capture("app_settings", "advanced")

        if self.tab_link(self.FEATURE_FLAGS_TAB).count() > 0:
            self.validate_feature_flags()
            shots.capture("app_settings", "feature_flags")

"""Page object for Robot Settings on the robot detail page."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

from automation.app_helpers.app_readiness import dismiss_blocking_ui
from automation.app_helpers.screenshot_helper import ScreenshotHelper
from automation.app_pages.base_app.app_base_page import AppBasePage
from automation.app_pages.base_app.devices_page import DevicesPage


class RobotSettingsPage(AppBasePage):
    """Robot Settings tabs — Calibration, Networking, Camera, and Advanced."""

    PAGE_HEADING = "Robot Settings"
    ABOUT_CALIBRATION = "About Calibration"
    PIPETTE_CALIBRATIONS = "Pipette Calibrations"
    PIPETTE_OFFSET_CALIBRATIONS = "Pipette Offset Calibrations"
    WIFI_HEADING = "Wi-Fi"
    ROBOT_NAME = "Robot Name"
    ROBOT_SERVER_VERSION = "Robot Server Version"
    PAUSE_PROTOCOL = "Pause protocol when robot door opens"
    GANTRY_HOMING = "Home Gantry on Restart"
    JUPYTER_NOTEBOOK = "Jupyter Notebook"
    UPDATE_ROBOT_SOFTWARE = "Update robot software manually with a local file (.zip)"
    DEVICE_RESET = "Device Reset"
    REINSTALL = "reinstall"
    RENAME_ROBOT = "Rename robot"
    CHOOSE_RESET_SETTINGS = "Choose reset settings"
    RENAME_ROBOT_SLIDEOUT = "Rename Robot"
    DEVICE_RESET_SLIDEOUT = "Device Reset"
    CAMERA_STATUS = "Camera Status"
    LIVE_VIDEO = "Live video"
    ERROR_IMAGE_CAPTURE = "Error image capture"
    USAGE_SETTINGS = "Usage Settings"

    TABS = (
        ("Calibration", "calibration"),
        ("Networking", "networking"),
        ("Camera", "camera"),
        ("Advanced", "advanced"),
    )

    def __init__(self, page: Page, *, robot_name: str) -> None:
        """Bind the Playwright page and target robot display name."""
        super().__init__(page)
        self.robot_name = robot_name

    @property
    def robot_settings_url(self) -> re.Pattern[str]:
        """Hash route for any Robot Settings tab."""
        return re.compile(rf"#/devices/{re.escape(self.robot_name)}/robot-settings")

    @property
    def page_heading(self) -> Locator:
        """Page title — scoped to Robot Settings content, not the breadcrumb."""
        return self.page.locator('[class*="RobotSettings"]').get_by_text(self.PAGE_HEADING, exact=True)

    def tab_link(self, name: str, slug: str) -> Locator:
        """Return the RoundTab link for a Robot Settings tab."""
        return self.page.locator(f'a[href*="robot-settings/{slug}"]').get_by_text(name, exact=True)

    def navigate(self) -> None:
        """Open Robot Settings from the robot detail overflow menu."""
        devices = DevicesPage(self.page, robot_name=self.robot_name)
        if not re.search(rf"#/devices/{re.escape(self.robot_name)}", self.page.url):
            devices.navigate()
        else:
            dismiss_blocking_ui(self.page)
        devices.open_robot_settings()
        expect(self.page).to_have_url(self.robot_settings_url)
        expect(self.page_heading).to_be_visible()

    def open_tab(self, name: str, slug: str) -> bool:
        """Click a Robot Settings tab and wait for its URL slug."""
        tab = self.tab_link(name, slug)
        if tab.count() == 0:
            return False
        tab.scroll_into_view_if_needed()
        tab.click()
        self.page.wait_for_url(f"**/robot-settings/{slug}")
        return True

    def _camera_status_switch(self) -> Locator:
        """Return the Camera Status toggle on the Camera tab."""
        return self.page.get_by_role("switch", name=self.CAMERA_STATUS)

    def _exercise_switch(self, switch: Locator) -> None:
        """Flip a switch once, then leave it in the on/checked state."""
        switch.click()
        if not switch.is_checked():
            switch.click()

    def validate_calibration_about(self) -> None:
        """T69745: Calibration > About Calibration. Manual inspection required."""
        self.open_tab("Calibration", "calibration")
        ScreenshotHelper(self.page).capture("robot_settings", "calibration_about")
        print("Applitoools diff expected, alert if significantly different")

    def validate_calibration_pipettes(self) -> None:
        """T69746: Calibration > Pipette Calibrations."""
        print("Pipette Calibraiton covered by validate_calibration_about")

    def validate_networking(self) -> None:
        """T69747: Networking."""
        self.open_tab("Networking", "networking")
        ScreenshotHelper(self.page).capture("robot_settings", "networking")
        print("Networking screenshot, to validate credentials")
        print("ToDo: Disconnect from Wi-Fi and check USB and Ethernet")

    def validate_privacy(self) -> None:
        """T69748: Privacy — validated via Camera usage controls"""
        shots = ScreenshotHelper(self.page)
        self.open_tab("Camera", "camera")
        shots.capture("robot_settings", "camera")

        self._exercise_switch(self._camera_status_switch())
        shots.capture("robot_settings", "camera_status")

        # App currently labels both Live video and Error image capture toggles
        # as "Live video" — use role + index, not a broad div filter.
        live_switches = self.page.get_by_role("switch", name=self.LIVE_VIDEO)
        for index in range(live_switches.count()):
            self._exercise_switch(live_switches.nth(index))
        shots.capture("robot_settings", "camera_usage_toggled")

    def validate_advanced_robot_name(self) -> None:
        """T69749: Advanced > Robot Name."""
        self.open_tab("Advanced", "advanced")
        expect(self.page.get_by_text(self.ROBOT_NAME, exact=True)).to_be_visible()
        rename = self.page.get_by_role("button", name=self.RENAME_ROBOT)
        expect(rename).to_be_visible()
        rename.click()
        expect(self.page.get_by_test_id(f"Slideout_title_{self.RENAME_ROBOT_SLIDEOUT}")).to_be_visible()
        self.close_slideout_by_title(self.RENAME_ROBOT_SLIDEOUT)

    def validate_advanced_robot_server_version(self) -> None:
        """T69750: Advanced > Robot server Version."""
        self.open_tab("Advanced", "advanced")
        expect(self.page.get_by_text(self.ROBOT_SERVER_VERSION, exact=True)).to_be_visible()

    def validate_advanced_pause_on_door_open(self) -> None:
        """T69751: Advanced > Pause protocol when robot door opens (OT-2 only)."""
        self.open_tab("Advanced", "advanced")
        expect(self.page.get_by_text(self.PAUSE_PROTOCOL, exact=True)).to_be_visible()
        expect(self.page.get_by_role("switch", name=self.PAUSE_PROTOCOL)).to_be_visible()

    def validate_advanced_gantry_homing(self) -> None:
        """Home gantry from robot detail overflow (not Advanced Settings toggle)."""
        DevicesPage(self.page, robot_name=self.robot_name).home_gantry()
        # Session-scoped robot_settings tests continue on Robot Settings afterward.
        self.navigate()

    def validate_advanced_jupyter_notebook(self) -> None:
        """T69753: Advanced > Jupyter Notebook."""
        self.open_tab("Advanced", "advanced")
        expect(self.page.get_by_text(self.JUPYTER_NOTEBOOK, exact=True)).to_be_visible()
        expect(self.page.get_by_text("Launch Jupyter Notebook", exact=True)).to_be_visible()

    def validate_advanced_update_robot_software(self) -> None:
        """T69754: Advanced > Update robot software."""
        self.open_tab("Advanced", "advanced")
        expect(self.page.get_by_text(self.UPDATE_ROBOT_SOFTWARE, exact=True)).to_be_visible()
        expect(self.page.get_by_role("button", name="Browse file system")).to_be_visible()

    def validate_advanced_robot_server_reinstall(self) -> None:
        """T69756: Advanced > Robot Server Reinstall."""
        self.open_tab("Advanced", "advanced")
        reinstall = self.page.get_by_role("button", name=self.REINSTALL)
        up_to_date = self.page.get_by_text("Up to date", exact=True)
        expect(reinstall.or_(up_to_date)).to_be_visible()

    def validate_analytics(self) -> None:
        """Analytics: Camera usage settings on the Camera tab."""
        self.open_tab("Camera", "camera")
        usage = self.page.get_by_text(self.USAGE_SETTINGS, exact=True)
        if usage.count() == 0:
            expect(self.page.get_by_text(self.CAMERA_STATUS, exact=True)).to_be_visible()
            return
        expect(usage).to_be_visible()

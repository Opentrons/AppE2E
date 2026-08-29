"""Page object for Robot Settings on the robot detail page."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

from automation.app_helpers.app_readiness import dismiss_blocking_ui
from automation.app_helpers.screenshot_helper import ScreenshotHelper
from automation.app_pages.base_app.app_base_page import AppBasePage
from automation.app_pages.base_app.devices_page import DevicesPage
from automation.app_pages.components import Banner, RoundTabBar, ToggleSwitch


class RobotSettingsPage(AppBasePage):
    """Robot Settings tabs for a connected Flex."""

    PAGE_HEADING = "Robot Settings"
    ABOUT_CALIBRATION = "About Calibration"
    PIPETTE_CALIBRATIONS = "Pipette Calibrations"
    PIPETTE_OFFSET_CALIBRATIONS = "Pipette Offset Calibrations"
    WIFI_HEADING = "Wi-Fi"
    ROBOT_NAME = "Robot Name"
    ROBOT_SERVER_VERSION = "Robot Server Version"
    PAUSE_PROTOCOL = "Pause protocol when robot door opens"
    JUPYTER_NOTEBOOK = "Jupyter Notebook"
    LAUNCH_JUPYTER_NOTEBOOK = "Launch Jupyter Notebook"
    UPDATE_ROBOT_SOFTWARE = "Update robot software manually with a local file (.zip)"
    DEVICE_RESET = "Device Reset"
    REINSTALL = "reinstall"
    # App renders this label lowercase (RobotServerVersion).
    UP_TO_DATE = "up to date"
    RENAME_ROBOT = "Rename robot"
    CHOOSE_RESET_SETTINGS = "Choose reset settings"
    RENAME_ROBOT_SLIDEOUT = "Rename Robot"
    DEVICE_RESET_SLIDEOUT = "Device Reset"
    CAMERA_STATUS = "Camera Status"
    LIVE_VIDEO = "Live video"
    # Visible Usage Settings title; Robot Settings wrongly reuses Live video as aria-label.
    ERROR_IMAGE_CAPTURE = "Error image capture"
    USAGE_SETTINGS = "Usage Settings"

    # Device Reset slideout (Flex calibration / run-history options).
    CLEAR_PIPETTE_CALIBRATION = "Clear pipette calibration"
    CLEAR_GRIPPER_CALIBRATION = "Clear gripper calibration"
    CLEAR_MODULE_CALIBRATION = "Clear module calibration"
    CLEAR_PROTOCOL_RUN_HISTORY = "Clear protocol run history"
    CLEAR_LABWARE_OFFSET_DATA = "Clear labware offset data"
    CLEAR_DATA_AND_RESTART = "Clear data and restart robot"
    RESET_TO_FACTORY_TITLE = "Reset to factory settings?"
    CONFIRM_RESET = "Confirm"
    FLEX_CALIBRATION_RESET_OPTIONS = (
        CLEAR_PIPETTE_CALIBRATION,
        CLEAR_GRIPPER_CALIBRATION,
        CLEAR_MODULE_CALIBRATION,
        CLEAR_PROTOCOL_RUN_HISTORY,
        CLEAR_LABWARE_OFFSET_DATA,
    )
    # Robot restart after clear can take a long time on hardware.
    DEVICE_RESET_NAV_TIMEOUT_MS = 60_000

    TABS = (
        ("Calibration", "calibration"),
        ("Networking", "networking"),
        ("Camera", "camera"),
        ("File manager", "file-manager"),
        ("Advanced", "advanced"),
        ("Feature Flags", "feature-flags"),
    )

    def __init__(self, page: Page, *, robot_name: str) -> None:
        """Bind the Playwright page and target robot display name."""
        super().__init__(page)
        self.robot_name = robot_name
        self.tabs = RoundTabBar(page, "robot-settings")

    @property
    def robot_settings_url(self) -> re.Pattern[str]:
        """Hash route for any Robot Settings tab."""
        return re.compile(rf"#/devices/{re.escape(self.robot_name)}/robot-settings")

    @property
    def page_heading(self) -> Locator:
        """Page title — scoped to the header, not the breadcrumb crumb."""
        scope = self.page.locator('[data-sentry-component="RobotSettings"]')
        return scope.get_by_text(self.PAGE_HEADING, exact=True).first

    def tab_link(self, name: str, slug: str) -> Locator:
        """Return the RoundTab link for a Robot Settings tab."""
        return self.tabs.tab(name, slug)

    def busy_warning(self) -> str | None:
        """Return the busy-control warning text when the banner is present."""
        banner = Banner(self.page, "warning")
        if banner.locator.count() == 0 or not banner.locator.is_visible():
            return None
        return banner.text()

    def navigate(self, *, tab: tuple[str, str] | None = None) -> None:
        """Open Robot Settings (overflow), optionally a specific tab like Advanced."""
        dismiss_blocking_ui(self.page)
        if not self.robot_settings_url.search(self.page.url):
            devices = DevicesPage(self.page, robot_name=self.robot_name)
            if not re.search(rf"#/devices/{re.escape(self.robot_name)}", self.page.url):
                devices.navigate()
            devices.open_robot_settings()
            expect(self.page).to_have_url(self.robot_settings_url)
        expect(self.page_heading).to_be_visible()
        if tab is not None:
            self.open_tab(*tab)

    def open_tab(self, name: str, slug: str) -> None:
        """Click a Robot Settings tab and wait for its URL slug."""
        self.tabs.open(name, slug)

    def open_feature_flags(self) -> bool:
        """Open the dev-gated Feature Flags tab when it is available."""
        tab = self.tab_link("Feature Flags", "feature-flags")
        if tab.count() == 0:
            return False
        self.open_tab("Feature Flags", "feature-flags")
        return True

    def _exercise_switch(self, aria_label: str) -> None:
        """Flip a switch once, then leave it in the on/checked state."""
        switch = ToggleSwitch(self.page, aria_label)
        switch.toggle()
        switch.turn_on()

    def _exercise_camera_usage_switch(self, row_title: str) -> None:
        """Flip a Usage Settings row switch (Robot Settings reuses Live video aria-labels)."""
        usage = self.page.locator('[data-sentry-component="RobotSettingsCameraUsage"]')
        row = usage.locator("div").filter(has=self.page.get_by_text(row_title, exact=True)).first
        switch = row.get_by_role("switch")
        expect(switch).to_be_visible()
        was_on = switch.get_attribute("aria-checked") == "true"
        switch.click()
        expect(switch).to_have_attribute("aria-checked", "false" if was_on else "true")
        if switch.get_attribute("aria-checked") != "true":
            switch.click()
        expect(switch).to_have_attribute("aria-checked", "true")

    def validate_calibration_about(self) -> None:
        """T69745: Calibration > About Calibration. Manual inspection required."""
        self.open_tab("Calibration", "calibration")
        ScreenshotHelper(self.page).capture("robot_settings", "calibration_about")
        print("Applitoools diff expected, alert if significantly different")

    def validate_calibration_pipettes(self) -> None:
        """T69746: Calibration > Pipette Calibrations."""
        print("Pipette Calibraiton covered by validate_calibration_about")

    def validate_networking(self) -> None:
        """T69747: Select the Networking RoundTab and capture a screenshot."""
        self.open_tab("Networking", "networking")
        tab = self.page.locator(
            '[data-sentry-component="RoundTab"]'
            f'[href="#/devices/{self.robot_name}/robot-settings/networking"]'
            '[aria-current="page"]'
        )
        expect(tab).to_have_text("Networking")
        ScreenshotHelper(self.page).capture("robot_settings", "networking")

    def validate_privacy(self) -> None:
        """T69748: Camera tab — enable Camera Status, exercise usage toggles, screenshot.

        Usage Settings (Live video / Error image capture) and Camera Controls are
        only rendered while Camera Status is on — enable first, then exercise them.
        """
        shots = ScreenshotHelper(self.page)
        self.open_tab("Camera", "camera")
        camera = self.page.locator('[data-sentry-component="RobotSettingsCamera"]')
        expect(camera.get_by_text(self.CAMERA_STATUS, exact=True).first).to_be_visible()
        shots.capture("robot_settings", "camera")

        self._exercise_switch(self.CAMERA_STATUS)
        ToggleSwitch(self.page, self.CAMERA_STATUS).turn_on()
        shots.capture("robot_settings", "camera_status")

        expect(camera.get_by_text(self.USAGE_SETTINGS, exact=True)).to_be_visible()
        self._exercise_camera_usage_switch(self.LIVE_VIDEO)
        self._exercise_camera_usage_switch(self.ERROR_IMAGE_CAPTURE)
        shots.capture("robot_settings", "camera_usage_toggled")

    # Rename slideout rejects the current name (already-exists / not dirty enough).
    RENAME_TEST_SUFFIX = "TEST"
    MAX_ROBOT_NAME_LEN = 17

    def read_displayed_robot_name(self) -> str:
        """Return the name shown under Advanced > Robot Name (may differ from fixture)."""
        scope = self.page.locator('[data-sentry-component="DisplayRobotName"]')
        label = scope.get_by_text(self.ROBOT_NAME, exact=True)
        expect(label).to_be_visible()
        value = scope.locator("p").filter(has_not_text=self.ROBOT_NAME).first
        expect(value).to_be_visible()
        return value.inner_text().strip()

    def read_robot_serial(self) -> str:
        """Return the read-only Flex serial from Advanced > Robot Information."""
        self.navigate(tab=("Advanced", "advanced"))
        scope = self.page.locator('[data-sentry-component="RobotInformation"]')
        label = scope.get_by_text("Robot Serial Number", exact=True)
        expect(label).to_be_visible()
        return label.locator("..").locator("p").last.inner_text().strip()

    def read_robot_server_version(self) -> str:
        """Return the read-only Robot Server Version from Advanced."""
        self.navigate(tab=("Advanced", "advanced"))
        scope = self.page.locator('[data-sentry-component="RobotServerVersion"]')
        label = scope.get_by_text(self.ROBOT_SERVER_VERSION, exact=True)
        expect(label).to_be_visible()
        return label.locator("..").locator("p").first.inner_text().strip()

    def _name_with_test_suffix(self, name: str) -> str:
        """Return ``{name}TEST`` capped to the app's 17-character alphanumeric limit."""
        base = re.sub(r"[^a-zA-Z0-9]", "", name)
        suffix = self.RENAME_TEST_SUFFIX
        return f"{base[: self.MAX_ROBOT_NAME_LEN - len(suffix)]}{suffix}"

    def _open_rename_slideout(self) -> None:
        """Click Advanced > Rename robot and wait for the slideout textbox."""
        open_rename = self.page.get_by_role("button", name=self.RENAME_ROBOT)
        expect(open_rename).to_be_visible()
        open_rename.click()
        # App 4.x Slideout dropped ``Slideout_title_*`` — wait on title text / input.
        expect(self.page.get_by_text(self.RENAME_ROBOT_SLIDEOUT, exact=True)).to_be_visible()
        expect(self._rename_robot_name_input()).to_be_visible()

    def _rename_robot_name_input(self) -> Locator:
        """Robot Name textbox inside the Rename slideout (label also appears on Advanced)."""
        return self.page.get_by_role("textbox", name=self.ROBOT_NAME)

    def _rename_robot_submit(self) -> Locator:
        """Footer Rename robot button in the slideout (not the Advanced-tab opener)."""
        return (
            self.page.locator("div")
            .filter(has_text=re.compile(rf"^{re.escape(self.RENAME_ROBOT)}$"))
            .get_by_role("button")
        )

    def submit_robot_rename(self, new_name: str) -> None:
        """Fill the Rename slideout and submit; lands on Devices with the new name."""
        name_input = self._rename_robot_name_input()
        expect(name_input).to_be_visible()
        name_input.click()
        name_input.fill(new_name)
        submit = self._rename_robot_submit()
        expect(submit).to_be_enabled()
        submit.click()
        expect(self.page).to_have_url(
            DevicesPage.DEVICES_LANDING_URL,
            timeout=self.DEVICE_RESET_NAV_TIMEOUT_MS,
        )
        self.robot_name = new_name

    def validate_advanced_robot_name(self) -> None:
        """T69749: Advanced > Robot Name — rename to ``{robot}TEST``, then restore.

        Reads the displayed name first: the form rejects renaming to the same name, and a
        prior run may have left the robot as ``{robot}TEST``.
        """
        self.navigate(tab=("Advanced", "advanced"))
        expect(self.page.get_by_text(self.ROBOT_NAME, exact=True).first).to_be_visible()

        configured_name = self.robot_name
        current_name = self.read_displayed_robot_name()
        self.robot_name = current_name
        test_name = self._name_with_test_suffix(configured_name)

        # Leftover ``{robot}TEST`` from a previous run — restore before the round-trip.
        if current_name == test_name:
            self._open_rename_slideout()
            self.submit_robot_rename(configured_name)
            self.navigate(tab=("Advanced", "advanced"))
            current_name = self.read_displayed_robot_name()
            self.robot_name = current_name

        if current_name == test_name:
            raise AssertionError(f"Robot name is still {test_name!r}; cannot rename to the same name")

        self._open_rename_slideout()
        self.submit_robot_rename(test_name)

        self.navigate(tab=("Advanced", "advanced"))
        self._open_rename_slideout()
        self.submit_robot_rename(configured_name)
        self.navigate(tab=("Advanced", "advanced"))
        expect(self.page.get_by_text(configured_name, exact=True).first).to_be_visible()

    def validate_advanced_robot_server_version(self) -> None:
        """T69750: Advanced > Robot server Version."""
        self.navigate(tab=("Advanced", "advanced"))
        expect(self.page.get_by_text(self.ROBOT_SERVER_VERSION, exact=True)).to_be_visible()

    def validate_advanced_pause_on_door_open(self) -> None:
        """T69751: Advanced > Pause protocol when robot door opens (OT-2 only)."""
        self.navigate(tab=("Advanced", "advanced"))
        expect(self.page.get_by_text(self.PAUSE_PROTOCOL, exact=True)).to_be_visible()
        expect(self.page.get_by_role("switch", name=self.PAUSE_PROTOCOL)).to_be_visible()

    def validate_advanced_jupyter_notebook(self) -> None:
        """T69753: Advanced > Jupyter Notebook (below the fold on Advanced)."""
        self.navigate(tab=("Advanced", "advanced"))
        heading = self.page.get_by_text(self.JUPYTER_NOTEBOOK, exact=True)
        launch = self.page.get_by_role("button", name=self.LAUNCH_JUPYTER_NOTEBOOK)
        heading.scroll_into_view_if_needed()
        expect(heading).to_be_visible()
        expect(launch).to_be_visible()

    def validate_advanced_update_robot_software(self) -> None:
        """T69754: Advanced > Update robot software."""
        self.navigate(tab=("Advanced", "advanced"))
        heading = self.page.get_by_text(self.UPDATE_ROBOT_SOFTWARE, exact=True)
        heading.scroll_into_view_if_needed()
        expect(heading).to_be_visible()
        expect(self.page.get_by_role("button", name="Browse file system")).to_be_visible()

    def validate_advanced_robot_server_reinstall(self) -> None:
        """T69756: Advanced > Robot Server Reinstall."""
        self.navigate(tab=("Advanced", "advanced"))
        reinstall = self.page.get_by_role("button", name=self.REINSTALL)
        up_to_date = self.page.get_by_text(self.UP_TO_DATE, exact=True)
        expect(reinstall.or_(up_to_date)).to_be_visible()

    def validate_analytics(self) -> None:
        """Analytics: Camera usage settings on the Camera tab (requires camera on)."""
        self.open_tab("Camera", "camera")
        ToggleSwitch(self.page, self.CAMERA_STATUS).turn_on()
        usage = self.page.locator('[data-sentry-component="RobotSettingsCamera"]').get_by_text(
            self.USAGE_SETTINGS, exact=True
        )
        expect(usage).to_be_visible()
        self._exercise_camera_usage_switch(self.LIVE_VIDEO)
        self._exercise_camera_usage_switch(self.ERROR_IMAGE_CAPTURE)

    def open_device_reset_slideout(self) -> None:
        """Advanced > Device Reset > Choose reset settings."""
        self.navigate(tab=("Advanced", "advanced"))
        expect(self.page.get_by_text(self.DEVICE_RESET, exact=True)).to_be_visible()
        choose = self.page.get_by_role("button", name=self.CHOOSE_RESET_SETTINGS)
        expect(choose).to_be_visible()
        choose.scroll_into_view_if_needed()
        choose.click()
        expect(self.page.get_by_role("button", name=self.CLEAR_DATA_AND_RESTART)).to_be_visible()

    def reset_option_checkbox(self, label: str) -> Locator:
        """Return a Device Reset slideout checkbox by its visible label."""
        return self.page.get_by_role("checkbox", name=label)

    def select_reset_options(self, labels: tuple[str, ...] | None = None) -> None:
        """Check the given Device Reset options (default: Flex calibration + run data)."""
        for label in labels or self.FLEX_CALIBRATION_RESET_OPTIONS:
            box = self.reset_option_checkbox(label)
            expect(box).to_be_visible()
            if not box.is_checked():
                box.click()
            expect(box).to_be_checked()

    def confirm_device_reset(self) -> None:
        """Clear data and restart robot, confirm the warning modal, land on Devices."""
        clear_btn = self.page.get_by_role("button", name=self.CLEAR_DATA_AND_RESTART)
        expect(clear_btn).to_be_enabled()
        clear_btn.click()
        expect(self.page.get_by_text(self.RESET_TO_FACTORY_TITLE, exact=True)).to_be_visible()
        confirm = self.page.get_by_role("button", name=self.CONFIRM_RESET)
        expect(confirm).to_be_visible()
        confirm.click()
        expect(self.page).to_have_url(
            DevicesPage.DEVICES_LANDING_URL,
            timeout=self.DEVICE_RESET_NAV_TIMEOUT_MS,
        )

    def reset_flex_calibration_data(self) -> None:
        """Clear Flex pipette/gripper/module cal, run history, and labware offsets; restart."""
        from automation.app_helpers.test_progress import run_timed

        if not self.robot_settings_url.search(self.page.url):
            run_timed("Navigate to Robot Settings", self.navigate)
        run_timed("Open Device Reset slideout", self.open_device_reset_slideout)
        run_timed("Select Flex calibration / run-data reset options", self.select_reset_options)
        run_timed("Confirm clear data and restart robot", self.confirm_device_reset)

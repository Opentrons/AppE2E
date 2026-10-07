"""Flex ODD Robot Settings list."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page, Response, expect

from automation.app_helpers import odd_config_ipc
from automation.app_pages.odd.odd_settings import LanguageToggle
from automation.app_pages.odd.odd_shell import OddShell

_STATUS_LEDS = "RobotSettingButton_display_led_lights"
_AUTO_DOWNLOAD = "RobotSettingButton_automatically_download_updates"
_AUTO_DOWNLOAD_PATH = "update.automaticallyDownloadUpdates"
_SLEEP_PATH = "onDeviceDisplaySettings.sleepMs"
_BRIGHTNESS_PATH = "onDeviceDisplaySettings.brightness"
_SLEEP_TARGET_MS = {"3 minutes": 180_000, "5 minutes": 300_000}
_ON_OFF = re.compile(r"^(On|Off)$")
_DEV_TOOLS = "RobotSettingButton_enable_dev_tools"
_DEVICE_RESET = "RobotSettingButton_device_reset"
_CLEAR_ALL_STORED = "clearAllStoredData"
_CLEAR_DATA_BUTTON = "DeviceReset_clear_data_button"
# Selecting every visible option also sends these implicit resets.
_FULL_RESET_KEYS = (
    "pipetteOffsetCalibrations",
    "gripperOffsetCalibrations",
    "moduleCalibration",
    "runsHistory",
    "authorizedKeys",
    "onDeviceDisplay",
    "deckConfiguration",
)


def _is_disable_status_bar(response: Response) -> bool:
    """True for the POST that toggles the Flex status LED strip."""
    request = response.request
    if request.method != "POST":
        return False
    if urlparse(request.url).path.rstrip("/") != "/settings":
        return False
    try:
        body = request.post_data_json
    except Exception:
        return False
    return isinstance(body, dict) and body.get("id") == "disableStatusBar"


def _is_settings_reset(response: Response) -> bool:
    """True for ``POST /settings/reset`` from Clear all stored data."""
    request = response.request
    if request.method != "POST":
        return False
    return urlparse(request.url).path.rstrip("/") == "/settings/reset"


def _posted_bool(response: Response) -> bool:
    """Return the boolean ``value`` from a status-LED POST."""
    body = response.request.post_data_json
    if not isinstance(body, dict) or not isinstance(body.get("value"), bool):
        raise AssertionError(f"Status LED POST body was {body!r}")
    value = body["value"]
    assert isinstance(value, bool)
    return value


class OddSettingsPage(OddShell):
    """Robot Settings list and the drill-in screens that replace it in place.

    Toggle rows (LED lights, dev tools, and similar) stay on the list.
    Use ``open_setting`` for rows that push a child screen with a back button,
    such as Network settings or Touchscreen sleep.
    """

    def __init__(self, page: Page) -> None:
        """Bind the Playwright page for the remote ODD window."""
        super().__init__(page)

    def open(self) -> None:
        """Open Robot Settings from the top nav."""
        self.open_settings()

    def setting_button(self, name: str) -> Locator:
        """A settings row. The accessible name also includes the subtitle."""
        return self.page.get_by_role("button", name=name)

    def expect_settings_list(self) -> None:
        """Assert the settings list is showing."""
        expect(self.setting_button("Network settings")).to_be_visible(timeout=15_000)
        expect(self.page.get_by_test_id("RobotSettingButton_robot_system_version")).to_be_visible()

    def open_setting(self, name: str) -> None:
        """Open a settings row that navigates to a child screen."""
        button = self.setting_button(name)
        self.press(button)
        expect(self.back_button).to_be_visible(timeout=15_000)

    def back(self) -> None:
        """Return from a settings child screen to the settings list."""
        self.press(self.back_button)
        expect(self.setting_button("Network settings")).to_be_visible(timeout=15_000)

    def expect_developer_tools_on(self) -> None:
        """Assert Developer tools is On.

        Alpha is hidden while this row is Off. Do not press the row here: the
        shell toggles the value on disk, and a stale Off tap stops the debug port.
        """
        _button, label = self._toggle_row(_DEV_TOOLS)
        if label != "On":
            raise AssertionError("Developer tools is Off, so the Alpha channel is hidden")

    def select_update_channel(self, label: str) -> None:
        """Open Update channel and select ``label`` (Stable, Beta, or Alpha).

        The radio input is hidden, so activate it directly. Alpha is only in
        the list while Developer tools is On.
        """
        self.open_setting("Update channel")
        radio = self.page.locator(f'input[type="radio"][id="{label}"]')
        expect(radio).to_have_count(1, timeout=15_000)
        radio.evaluate("element => element.click()")
        expect(radio).to_be_checked()

    def start_available_robot_update(self) -> None:
        """Robot system version → Update available → Update.

        An available release opens its notes modal on this screen. View update
        opens that modal when it is not already showing. Update leaves for the
        software update screen. This does not wait for the install to finish.
        """
        self.press(self.page.get_by_test_id("RobotSettingButton_robot_system_version"))
        available = self.page.get_by_text("Update available", exact=True)
        update = self.page.get_by_role("button", name="Update", exact=True)
        expect(available.or_(update).first).to_be_visible(timeout=15_000)
        if update.count() == 0 or not update.first.is_visible():
            self.press(self.page.get_by_role("button", name="View update", exact=True))
        self.press(update)
        expect(self.page).to_have_url(re.compile(r"update-robot"), timeout=30_000)
        expect(self.page.get_by_text("Update found!", exact=True)).to_be_visible(timeout=30_000)

    def _choose_sleep(self, label: str) -> None:
        """Select a sleep radio. The input is hidden, so activate it directly."""
        radio = self.page.locator(f'input[type="radio"][id="{label}"]')
        expect(radio).to_have_count(1, timeout=15_000)
        radio.evaluate("element => element.click()")

    def toggle_language(self) -> None:
        """Open Language, switch to 中文, confirm the translated header, and restore English (US)."""
        LanguageToggle(self.page).click_language()

    def _toggle_row(self, test_id: str) -> tuple[Locator, str]:
        """Return a settings row and the On/Off label inside it."""
        button = self.page.get_by_test_id(test_id)
        expect(button).to_be_visible(timeout=15_000)
        button.scroll_into_view_if_needed()
        label = button.get_by_text(_ON_OFF)
        expect(label).to_be_visible()
        text = label.inner_text().strip()
        if text not in {"On", "Off"}:
            raise AssertionError(f"{test_id} toggle label is {text!r}")
        return button, text

    def _confirm_documentation_if_needed(self) -> None:
        """Fill the audit note when access control asks for one."""
        heading = self.page.get_by_text("Documentation required", exact=True)
        try:
            heading.wait_for(state="visible", timeout=3_000)
        except Exception:
            return
        self.page.locator("textarea").fill("e2e settings check")
        self.press(self.page.get_by_test_id("ChildNavigation_Primary_Button"))
        expect(heading).to_be_hidden(timeout=15_000)

    def exercise_status_leds(self) -> str:
        """Toggle Status LEDs, confirm ``POST /settings``, and restore the original label.

        The row shows On while ``disableStatusBar`` is false. The tap posts the
        current lights-enabled flag, so On sends ``true`` and turns the strip off.
        """
        button, original = self._toggle_row(_STATUS_LEDS)
        flipped = "Off" if original == "On" else "On"
        posted_when_showing = {"On": True, "Off": False}
        changed = False
        try:
            with self.page.expect_response(_is_disable_status_bar, timeout=20_000) as first:
                self.press(button)
                changed = True
                self._confirm_documentation_if_needed()
            response = first.value
            assert response.ok
            assert _posted_bool(response) is posted_when_showing[original]
            expect(button.get_by_text(flipped, exact=True)).to_be_visible(timeout=15_000)
            return original
        finally:
            if changed:
                with self.page.expect_response(_is_disable_status_bar, timeout=20_000) as second:
                    self.press(button)
                    self._confirm_documentation_if_needed()
                restore = second.value
                assert restore.ok
                assert _posted_bool(restore) is posted_when_showing[flipped]
                expect(button.get_by_text(original, exact=True)).to_be_visible(timeout=15_000)

    def exercise_automatic_downloads(self) -> str:
        """Toggle automatic downloads, confirm the config IPC write, and restore.

        Requires :func:`odd_config_ipc.listen_for_config_updates` around the call.
        """
        button, original = self._toggle_row(_AUTO_DOWNLOAD)
        flipped = "Off" if original == "On" else "On"
        expected = original == "Off"
        changed = False
        try:
            odd_config_ipc.clear(self.page)
            self.press(button)
            changed = True
            value = odd_config_ipc.wait_for_value(self.page, _AUTO_DOWNLOAD_PATH)
            assert value is expected
            expect(button.get_by_text(flipped, exact=True)).to_be_visible(timeout=15_000)
            return original
        finally:
            if changed:
                odd_config_ipc.clear(self.page)
                self.press(button)
                restored = odd_config_ipc.wait_for_value(self.page, _AUTO_DOWNLOAD_PATH)
                assert restored is (original == "On")
                expect(button.get_by_text(original, exact=True)).to_be_visible(timeout=15_000)

    def exercise_touchscreen_sleep(self) -> str:
        """Pick a different sleep timeout, confirm ``sleepMs``, and restore the original radio.

        Requires :func:`odd_config_ipc.listen_for_config_updates` around the call.
        """
        self.open_setting("Touchscreen sleep")
        changed = False
        original_label = ""
        original_ms = 0
        try:
            checked = self.page.locator('input[type="radio"]:checked')
            expect(checked).to_have_count(1, timeout=15_000)
            original_label = checked.get_attribute("id") or ""
            original_ms = int(checked.get_attribute("value") or "0")
            target_label = "5 minutes" if original_label == "3 minutes" else "3 minutes"
            target_ms = _SLEEP_TARGET_MS[target_label]
            odd_config_ipc.clear(self.page)
            self._choose_sleep(target_label)
            changed = True
            value = odd_config_ipc.wait_for_value(self.page, _SLEEP_PATH)
            assert value == target_ms
            expect(self.page.locator('input[type="radio"]:checked')).to_have_value(str(target_ms))
            return original_label
        finally:
            try:
                if changed:
                    odd_config_ipc.clear(self.page)
                    self._choose_sleep(original_label)
                    restored = odd_config_ipc.wait_for_value(self.page, _SLEEP_PATH)
                    assert restored == original_ms
            finally:
                if self.back_button.count() > 0 and self.back_button.is_visible():
                    self.back()

    def exercise_touchscreen_brightness(self) -> int:
        """Step brightness once, confirm the config IPC write, and step back.

        Requires :func:`odd_config_ipc.listen_for_config_updates` around the call.
        Returns the brightness level after the first step.
        """
        self.open_setting("Touchscreen brightness")
        changed = False
        step = 0
        new_level = 0
        try:
            increase = self.page.get_by_test_id("TouchscreenBrightness_increase")
            decrease = self.page.get_by_test_id("TouchscreenBrightness_decrease")
            expect(increase).to_be_visible(timeout=15_000)
            expect(decrease).to_be_visible()
            if not increase.is_disabled():
                control = increase
                step = 1
            elif not decrease.is_disabled():
                control = decrease
                step = -1
            else:
                raise AssertionError("Touchscreen brightness plus and minus are both disabled")
            odd_config_ipc.clear(self.page)
            self.press(control)
            changed = True
            value = odd_config_ipc.wait_for_value(self.page, _BRIGHTNESS_PATH)
            if isinstance(value, bool) or not isinstance(value, int):
                raise AssertionError(f"Brightness IPC value was {value!r}")
            assert 1 <= value <= 6
            new_level = value
            return new_level
        finally:
            try:
                if changed:
                    opposite = (
                        self.page.get_by_test_id("TouchscreenBrightness_decrease")
                        if step == 1
                        else self.page.get_by_test_id("TouchscreenBrightness_increase")
                    )
                    odd_config_ipc.clear(self.page)
                    self.press(opposite)
                    restored = odd_config_ipc.wait_for_value(self.page, _BRIGHTNESS_PATH)
                    assert restored == new_level - step
            finally:
                if self.back_button.count() > 0 and self.back_button.is_visible():
                    self.back()

    def clear_all_stored_data_and_restart(self) -> None:
        """Device reset → Clear all stored data → Clear data and restart robot → Confirm.

        Confirms ``POST /settings/reset`` includes every stored-data option.
        The robot reboots after that request succeeds.
        """
        button = self.page.get_by_test_id(_DEVICE_RESET)
        expect(button).to_be_visible(timeout=15_000)
        self.press(button)
        expect(self.back_button).to_be_visible(timeout=15_000)
        expect(self.page.get_by_text("Resets cannot be undone", exact=True)).to_be_visible()

        checkbox = self.page.locator(f'input[type="checkbox"][id="{_CLEAR_ALL_STORED}"]')
        expect(checkbox).to_have_count(1, timeout=15_000)
        checkbox.evaluate("element => element.click()")
        expect(checkbox).to_be_checked()

        clear = self.page.get_by_test_id(_CLEAR_DATA_BUTTON)
        expect(clear).to_be_enabled()
        self.press(clear)
        expect(self.page.get_by_text("Are you sure you want to reset your device?", exact=True)).to_be_visible()

        confirm = self.page.get_by_role("button", name="Confirm", exact=True)
        with self.page.expect_response(_is_settings_reset, timeout=60_000) as posted:
            self.press(confirm)
            try:
                self._confirm_documentation_if_needed()
            except PlaywrightError as error:
                if "closed" not in str(error).lower():
                    raise
        response = posted.value
        assert response.ok, response.status
        body = response.request.post_data_json
        if not isinstance(body, dict):
            raise AssertionError(f"POST /settings/reset body was {body!r}")
        missing = [key for key in _FULL_RESET_KEYS if body.get(key) is not True]
        if missing:
            raise AssertionError(f"POST /settings/reset omitted {missing}; body={body!r}")

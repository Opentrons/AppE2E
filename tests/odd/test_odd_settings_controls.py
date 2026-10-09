"""Confirm ODD Robot Settings writes, then put each control back."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from automation.app_helpers.odd_config_ipc import listen_for_config_updates
from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages.odd import OddSettingsPage

# Same lab account as the Compliance Ready login smoke.
_USERNAME = "testadmin"
_PASSWORD = "testadminpassword"


@pytest.mark.odd
@pytest.mark.workflow(
    group="odd_settings",
    section="Robot settings",
    label="Toggle LEDs, downloads, sleep, and brightness",
    order=10,
)
def test_odd_settings_controls(run_odd_app: Page) -> None:
    """Toggle Status LEDs, automatic downloads, sleep, and brightness, then restore each one."""
    page = run_odd_app
    settings = OddSettingsPage(page)

    log_step("Sign in when the touchscreen is locked")
    settings.log_in_if_locked(_USERNAME, _PASSWORD)
    log_done("Touchscreen is unlocked")

    log_step("Open Robot Settings")
    settings.open()
    settings.expect_settings_list()
    log_done("Robot Settings list visible")

    with listen_for_config_updates(page):
        log_step("Status LEDs — POST /settings and restore")
        led_label = settings.exercise_status_leds()
        log_done(f"Status LEDs restored to {led_label}")

        log_step("Automatically download updates — config IPC and restore")
        download_label = settings.exercise_automatic_downloads()
        log_done(f"Automatically download updates restored to {download_label}")

        log_step("Touchscreen sleep — config IPC and restore")
        sleep_label = settings.exercise_touchscreen_sleep()
        log_done(f"Touchscreen sleep restored to {sleep_label}")

        log_step("Touchscreen brightness — config IPC and restore")
        brightness = settings.exercise_touchscreen_brightness()
        log_done(f"Touchscreen brightness stepped to {brightness} and restored")

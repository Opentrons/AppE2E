"""Clear all stored data on the Flex ODD and restart the robot."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages.odd import OddSettingsPage

# Same lab account as the Compliance Ready login smoke.
_USERNAME = "testadmin"
_PASSWORD = "testadminpassword"


@pytest.mark.odd
@pytest.mark.workflow(
    group="odd_device_reset",
    section="Device reset",
    label="Clear all stored data and restart",
    order=10,
)
def test_odd_clear_all_stored_data(run_odd_app: Page) -> None:
    """Settings → Device reset → Clear all stored data → Clear data and restart robot.

    Confirms the reset, then waits for ``POST /settings/reset``. The robot reboots.
    The setup screens that follow are ``test_odd_initial_post_device_reset``.
    """
    page = run_odd_app
    settings = OddSettingsPage(page)

    log_step("Sign in when the touchscreen is locked")
    settings.log_in_if_locked(_USERNAME, _PASSWORD)
    log_done("Touchscreen is unlocked")

    log_step("Open Robot Settings")
    settings.open()
    settings.expect_settings_list()
    robot_label = settings.dashboard_link.inner_text().strip()
    if "QA1" not in robot_label:
        raise AssertionError(f"Refusing device reset: touchscreen name is {robot_label!r}, expected QA1")
    log_done(f"Robot Settings list visible on {robot_label}")

    log_step("Device reset → Clear all stored data → Clear data and restart robot")
    settings.clear_all_stored_data_and_restart()
    log_done("POST /settings/reset accepted; robot is restarting")

"""Switch the ODD update channel to Alpha and start the offered robot update.

Developer tools must already be On. This test does not toggle that row, and it
does not reload the touchscreen page. It stops once the update screen is up.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages.odd import OddSettingsPage


@pytest.mark.odd
@pytest.mark.timeout(180)
@pytest.mark.workflow(
    group="odd_update",
    section="System update",
    label="Switch to Alpha and start robot update",
    order=10,
)
def test_odd_alpha_channel_update(run_odd_app: Page) -> None:
    """Update channel → Alpha → back → Robot system version → Update."""
    settings = OddSettingsPage(run_odd_app)

    log_step("Open Robot Settings")
    settings.open()
    settings.expect_settings_list()
    settings.expect_developer_tools_on()
    log_done("Developer tools is On")

    log_step("Update channel → Alpha")
    settings.select_update_channel("Alpha")
    log_done("Alpha is selected")

    log_step("Back to Robot Settings")
    settings.back()
    log_done("Settings list is showing")

    log_step("Robot system version → Update available → Update")
    settings.start_available_robot_update()
    log_done("Update screen is up")

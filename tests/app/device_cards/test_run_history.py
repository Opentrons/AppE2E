"""Run History tab on robot detail."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages import RunHistoryPage

ROBOT_DETAIL_REQUIRED = "tests/app/device_cards/test_devices_nav.py::test_robot_detail_from_devices_list"


@pytest.mark.workflow(
    group="devices",
    section="Run History",
    label="Review and download run history",
    order=40,
    requires=ROBOT_DETAIL_REQUIRED,
)
def test_run_history(
    run_local_app: Page,
    robot_name: str,
    device_details_tabs: bool,
) -> None:
    """Open Run History and assert the Download all control is available."""
    if not device_details_tabs:
        pytest.skip("Run History tab requires the Device Details tabs layout.")

    log_step(f"Open Run History for '{robot_name}'")
    history = RunHistoryPage(run_local_app, robot_name=robot_name)
    history.open()
    expect(run_local_app.get_by_role("button", name="Download all")).to_be_visible()
    log_done("Run History reviewed")

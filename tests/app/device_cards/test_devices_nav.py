"""Devices list to robot detail navigation.

Robot Settings test plan (``device_cards`` suite — runs before card exercises):

1. T69745 — Robot Settings > Calibration > About Calibration
2. T69746 — Robot Settings > Calibration > Pipette Calibrations
3. T69747 — Robot Settings > Networking
4. T69748 — Robot Settings > Privacy
5. T69749 — Robot Settings > Advanced > Robot Name
6. T69750 — Robot Settings > Advanced > Robot server Version
7. T69751 — Robot Settings > Advanced > Pause protocol when robot door opens
8. Home gantry — Robot Overview overflow → Home gantry
   (only while no protocol run is loaded on the robot; protocol_run requires this)
9. T69753 — Robot settings > Advanced > Jupyter Notebook
10. T69754 — Robot Settings > Advanced > Update robot software
11. T69756 — Robot settings > Advanced > Robot Server Reinstall
12. Analytics — Robot and app analytics (robot settings context)

Device reset + calibrate lives in ``tests/app/calibration/test_calibration.py``.
"""

from __future__ import annotations

import pytest
from packaging.version import Version
from playwright.sync_api import Page

from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages import DevicesPage


@pytest.mark.workflow(
    group="devices",
    section="Navigation",
    label="Open robot detail from Devices",
    order=10,
)
def test_robot_detail_from_devices_list(
    run_local_app: Page,
    robot_name: str,
    app_version: Version,
    device_details_tabs: bool,
) -> None:
    """Navigate to robot detail — prerequisite for T69745–T69756 (``test_robot_settings``)."""
    log_step(f"Open Devices and select robot '{robot_name}' (app {app_version})")
    devices = DevicesPage(run_local_app, robot_name=robot_name)
    devices.navigate()
    log_done(f"Robot detail page loaded ({robot_name})")

    if device_details_tabs:
        log_step("Assert Device Details tabs (version-gated layout)")
        devices.expect_device_details_tabs_visible()
        log_done("Hardware / Deck Configuration / Run History tabs visible")
    else:
        log_step("Assert Device Details tabs absent (legacy single-page layout)")
        devices.expect_device_details_tabs_hidden()
        log_done("Device Details RoundTabs not present")

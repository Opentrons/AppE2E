"""Protocol run shell tabs and header."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from automation.app_helpers.protocol_run_target import ProtocolRunTarget
from automation.app_helpers.screenshot_helper import ScreenshotHelper
from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages import (
    ChooseRobotToRunProtocolSlideout,
    ProtocolRunPage,
    ProtocolsPage,
)

# Home gantry is disabled once a protocol run is loaded on the robot.
HOME_GANTRY_REQUIRED = (
    "tests/app/device_cards/test_robot_settings.py::test_home_gantry_from_overview_overflow"
)
PROTOCOL_RUN_TABS = "tests/app/nav/test_protocol_run_tabs.py::test_protocol_run_tabs"


@pytest.mark.workflow(
    group="protocol_run",
    section="Tabs",
    label="Screenshot protocol run tabs",
    order=10,
    requires=HOME_GANTRY_REQUIRED,
)
def test_protocol_run_tabs(
    run_local_app: Page,
    protocol_name: str,
    robot_name: str,
    screenshot_helper: ScreenshotHelper,
) -> None:
    """Create a run, then click and screenshot each present run-page tab."""
    page = run_local_app
    target = ProtocolRunTarget(protocol_name=protocol_name, robot_name=robot_name)

    log_step(f"Start setup for '{protocol_name}'")
    ProtocolsPage(page).start_setup(protocol_name)
    log_done("Start setup slideout opened")

    log_step(f"Select robot '{robot_name}' and proceed to run")
    ChooseRobotToRunProtocolSlideout(page).start_run(target)
    run_page = ProtocolRunPage(page, shots=screenshot_helper)
    run_page.wait_until_open()
    log_done("Protocol run page opened")

    log_step("Click and screenshot each run tab")
    run_page.capture_all_tabs()
    log_done("Protocol run tabs captured")


@pytest.mark.workflow(
    group="protocol_run",
    section="Header",
    label="Read run status and timer",
    order=20,
    requires=PROTOCOL_RUN_TABS,
)
def test_protocol_run_header(run_local_app: Page) -> None:
    """Read the run header status chip and run timer after tabs have opened a run."""
    run_page = ProtocolRunPage(run_local_app)
    run_page.wait_until_open()
    log_step("Read run status chip")
    variant, text = run_page.read_status()
    log_step(f"Status: {text!r} (variant={variant!r})")
    log_step("Read run timer")
    timer = run_page.read_run_time()
    log_step(f"Run timer: {timer!r}")
    log_done("Run header status and timer read")

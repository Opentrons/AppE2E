"""Device card tests start on the robot detail page."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from playwright.sync_api import Page

from automation.app_helpers.app_readiness import dismiss_blocking_ui
from automation.app_helpers.test_progress import log_done, log_step, make_suite_logstart
from automation.app_pages import DeviceCardsPage, DevicesPage

pytestmark = pytest.mark.device_cards


pytest_runtest_logstart = make_suite_logstart("device_cards")


@pytest.fixture(scope="session")
def device_cards(
    run_local_app: Page,
    robot_name: str,
    device_details_tabs: bool,
) -> Generator[DeviceCardsPage, None, None]:
    """Shared helper: navigate once, cache module inventory for all tests in this session."""
    log_step(f"Navigating to robot detail for '{robot_name}'")
    helper = DeviceCardsPage(run_local_app)
    devices = DevicesPage(run_local_app, robot_name=robot_name)
    devices.navigate()
    devices.open_hardware(use_tabs=device_details_tabs)
    dismiss_blocking_ui(run_local_app)
    log_done(f"On robot detail Hardware ({robot_name}, tabs={device_details_tabs})")
    log_step("Wait for module cards to finish loading")
    try:
        helper.wait_for_module_cards()
        log_done("Module cards ready")
    except TimeoutError:
        log_step("No enabled module cards detected — continuing")
    log_step("Read module serial numbers and firmware versions")
    helper.print_module_inventory()
    log_done("Module inventory printed")
    yield helper

"""Walk the Flex ODD setup screens that follow Clear all stored data.

Run this after ``test_odd_clear_all_stored_data``, once the touchscreen is
back on Choose Language or Welcome. It stops after Wi-Fi Continue.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages.odd import OddUnboxingPage

_SSID = "OPTRN-NYC1-ROBOTICS"
_PASSWORD = "r0B@t$2@"


@pytest.mark.odd
@pytest.mark.timeout(900)
@pytest.mark.workflow(
    group="odd_device_reset",
    section="Device reset",
    label="Welcome, language, and Wi-Fi after reset",
    order=20,
)
def test_odd_initial_post_device_reset(run_odd_app: Page, robot_ip: str) -> None:
    """Welcome, English (US), and Wi-Fi after a device reset.

    Closes a blocking toast (new module, or a server-version update) when one
    is covering the buttons. Wi-Fi Continue is allowed eight minutes because
    the robot can take at least five minutes to reconnect.
    """
    setup = OddUnboxingPage(run_odd_app)

    log_step("Wait for the setup screen after boot")
    setup.wait_for_setup_screen()
    log_done("Setup screen is up")

    log_step("Welcome, English (US), and Get started")
    setup.pass_opening_screens()
    log_done("Network type screen is up")

    log_step("Wi-Fi")
    setup.choose_wifi()
    log_done("Wi-Fi network list is up")

    log_step(f"Wait for {_SSID}")
    setup.select_network(_SSID)
    log_done(f"Selected {_SSID}")

    log_step("Continue")
    setup.continue_from_security()
    log_done("Wi-Fi password screen is up")

    log_step("Enter the Wi-Fi password and connect")
    setup.enter_password_and_connect(_PASSWORD)
    setup.expect_connecting(_SSID)
    log_done(f"Connecting to {_SSID}")

    log_step("Continue once Wi-Fi finishes connecting")
    setup.continue_when_connected(robot_ip)
    log_done("Left the Wi-Fi connection screen")

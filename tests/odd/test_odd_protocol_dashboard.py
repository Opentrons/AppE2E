"""Ensure three protocols are on the Flex, then exercise ODD protocol flows."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from playwright.sync_api import Page

from automation.app_helpers.app_odd_protocol_session import desktop_app
from automation.app_helpers.dev_robot_setup import ensure_robot_ip_discovered
from automation.app_helpers.robot_profiles import DEFAULT_HARDWARE_ROBOT_NAME
from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages import OddHomePage, OddProtocolOptions, OddProtocolsPage, ProtocolSection, ProtocolsPage

_PROTOCOL_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "protocols"
_PROTOCOL_1 = "Protocol 1: Temperature Module Disconnect Recovery Test"
_PROTOCOL_2 = "Protocol 2: Hardware API pick up and drop labware"
_SMOKE = "Flex Smoke Test - v2.29"
_PROTOCOLS = (
    (_PROTOCOL_1, _PROTOCOL_DIR / "test_tempdeck.py"),
    (_SMOKE, _PROTOCOL_DIR / "Flex_S_2_9_P200_96_GRIP_HS_MB_TC_TM_Overrides_smoke.py"),
    (_PROTOCOL_2, _PROTOCOL_DIR / "hardware_api_command.py"),
)
_PROTOCOL_NAMES = tuple(name for name, _ in _PROTOCOLS)

# Same lab account as the other ODD settings flows.
_USERNAME = "testadmin"
_PASSWORD = "testadminpassword"


def _send_protocols(page: Page, robot_ip: str, protocol_names: tuple[str, ...]) -> None:
    """Import any missing desktop copies and send them to the Flex."""
    robot_name = os.environ.get("ROBOT_NAME", DEFAULT_HARDWARE_ROBOT_NAME).strip()
    paths = dict(_PROTOCOLS)
    ensure_robot_ip_discovered(page, robot_name=robot_name, host=robot_ip, force=True)
    desktop_protocols = ProtocolsPage(page)
    for protocol_name in protocol_names:
        log_step(f"Check desktop Protocols for {protocol_name!r}")
        imported = desktop_protocols.ensure_protocol_imported(protocol_name, paths[protocol_name])
        log_done("Imported missing protocol" if imported else "Protocol already present on desktop")

        log_step(f"Send {protocol_name!r} to {robot_name}")
        desktop_protocols.send_protocol_to_flex(protocol_name, robot_name)
        log_done("Protocol sent to Flex")


@pytest.mark.odd
def test_odd_protocols(request: pytest.FixtureRequest, run_odd_app: Page, robot_ip: str) -> None:
    """Prep the three protocols, then walk dashboard, list, smoke details, pin, and delete.

    Deletes Protocol 1. Leaves the Flex Smoke Test pinned, with Protocol 2 still on the robot.
    """
    page = run_odd_app
    request.session.playwright_debug_page = page
    home = OddHomePage(page)
    protocols = OddProtocolsPage(page)
    section = ProtocolSection(page)
    options = OddProtocolOptions(page)

    log_step("Sign in when the touchscreen is locked")
    section.log_in_if_locked(_USERNAME, _PASSWORD)
    log_done("Touchscreen is unlocked")

    log_step("Check whether the three protocols are already on the ODD")
    protocols.open()
    protocols.wait_for_protocol_inventory()
    missing = protocols.missing_protocols(_PROTOCOL_NAMES)
    if not missing:
        log_done("protocols already added, proceed to the test")
    else:
        log_step(f"Missing on the ODD: {', '.join(missing)}")
        with desktop_app() as app_page:
            request.session.playwright_debug_page = app_page
            _send_protocols(app_page, robot_ip, missing)
        request.session.playwright_debug_page = page
        page.reload()
        section.log_in_if_locked(_USERNAME, _PASSWORD)
        protocols.open()
        protocols.expect_protocols(_PROTOCOL_NAMES)
        log_done("Protocols received on the ODD")

    log_step("Dashboard (ODD)")
    home.open_dashboard()
    home.expect_dashboard_content()
    log_done("Dashboard visible")

    log_step("All Protocols (ODD)")
    protocols.open()
    protocols.expect_protocol_list()
    protocols.expect_protocols(_PROTOCOL_NAMES)
    log_done("All Protocols list shows Protocol 1, Protocol 2, and Flex Smoke Test")

    log_step("Protocol Sorting (ODD)")
    protocols.exercise_sorting()
    log_done("Protocol Name, Last Run, and Date Added each sorted both ways")

    log_step("Protocol Setup Details on Smoke")
    section.select_protocol_name(_SMOKE)
    log_done("Flex Smoke Test details are open")

    log_step("Setup: Flex Smoke Test")
    section.expect_start_setup()
    log_done("Start setup is visible")

    log_step("Parameters")
    options.expect_smoke_parameters()
    log_done("Parameters shows Number of Stackers")

    log_step("Deck")
    options.deck()
    log_done("Deck map is visible")

    log_step("Liquids")
    options.liquids()
    log_done("Liquids shows Water")

    log_step("Pin a Protocol (ODD)")
    log_step("Pin Smoke test")
    section.pin_protocol()
    section.select_protocol_header()
    protocols.expect_protocol_pinned(_SMOKE)
    log_done("Flex Smoke Test is pinned")

    log_step("Delete a protocol (ODD)")
    log_step("Delete Protocol 1")
    section.select_protocol_name(_PROTOCOL_1)
    section.delete_protocol()
    section.expect_protocol_absent(_PROTOCOL_1)
    protocols.expect_protocols((_SMOKE, _PROTOCOL_2))
    log_done("Protocol 1 deleted; smoke test and Protocol 2 remain")

    log_step("Dashboard")
    home.open_dashboard()
    home.expect_dashboard_content()
    log_done("Dashboard visible")

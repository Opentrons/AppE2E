"""Exercise each ProtocolSection and OddProtocolOptions action on the Flex ODD."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages.odd.odd_protocol_section import OddProtocolOptions, ProtocolSection

# Same lab account as the other ODD settings flows.
_USERNAME = "testadmin"
_PASSWORD = "testadminpassword"

_SMOKE = "Flex Smoke Test - v2.29"
_PROTOCOL_1 = "Protocol 1: Temperature Module Disconnect Recovery Test"
_PROTOCOL_2 = "Protocol 2: Hardware API pick up and drop labware"


@pytest.mark.odd
def test_odd_protocol_section(run_odd_app: Page) -> None:
    """Walk protocol tabs, pin, unpin, and cancel, then delete Protocol 1.

    The Flex Smoke Test protocol is left on the robot.
    """
    page = run_odd_app
    section = ProtocolSection(page)
    options = OddProtocolOptions(page)

    log_step("Sign in when the touchscreen is locked")
    section.log_in_if_locked(_USERNAME, _PASSWORD)
    log_done("Touchscreen is unlocked")

    log_step("Open Protocols")
    section.select_protocol_header()
    expect(page.get_by_text(_SMOKE, exact=True)).to_be_visible()
    log_done("Protocols list is open and the smoke test is still present")

    log_step(f"Open {_PROTOCOL_2!r}")
    section.select_protocol_name(_PROTOCOL_2)
    log_done("Protocol 2 details are open")

    log_step("Summary tab")
    options.summary()
    log_done("Summary shows Date Added")

    log_step("Parameters tab")
    options.parameters()
    log_done("Parameters tab is showing")

    log_step("Hardware tab")
    options.Hardware()
    log_done("Hardware tab is showing")

    log_step("Pin Protocol 2")
    section.pin_protocol()
    log_done("Protocol 2 is pinned")

    log_step("Unpin Protocol 2")
    section.unpin_protocol()
    log_done("Protocol 2 is unpinned")

    log_step("Open delete confirmation, then cancel")
    section.open_delete_confirmation()
    options.cancel()
    expect(page.get_by_text(_PROTOCOL_2, exact=True)).to_be_visible()
    log_done("Cancel left Protocol 2 on the robot")

    log_step(f"Delete {_PROTOCOL_1!r}")
    section.select_protocol_header()
    section.select_protocol_name(_PROTOCOL_1)
    section.delete_protocol()
    expect(page.get_by_test_id("protocol_card").filter(has_text=_PROTOCOL_1)).to_have_count(0, timeout=15_000)
    expect(page.get_by_text(_SMOKE, exact=True)).to_be_visible()
    expect(page.get_by_text(_PROTOCOL_2, exact=True)).to_be_visible()
    log_done("Protocol 1 deleted; smoke test and Protocol 2 remain")

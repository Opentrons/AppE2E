"""Protocols page navigation and detail tabs."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages import ProtocolsPage


@pytest.mark.workflow(
    group="protocols",
    section="Protocol details",
    label="Open protocol details",
    order=10,
)
def test_protocol_opens_from_landing(run_local_app: Page, protocol_name: str) -> None:
    """Open a protocol from the landing list and assert detail URL loads."""
    log_step(f"Open Protocols landing and select '{protocol_name}'")
    ProtocolsPage(run_local_app).open(protocol_name)
    expect(run_local_app).to_have_url(ProtocolsPage.PROTOCOL_DETAIL_URL)
    log_done("Protocol detail page loaded")


@pytest.mark.workflow(
    group="protocols",
    section="Protocol details",
    label="Protocol detail tabs",
    order=20,
)
def test_protocol_detail_tabs(run_local_app: Page, protocol_name: str) -> None:
    """Open a protocol and click each present detail tab."""
    log_step(f"Open protocol '{protocol_name}'")
    protocols = ProtocolsPage(run_local_app)
    protocols.open(protocol_name)
    log_step("Click each detail tab")
    protocols.validate_all_tabs()
    log_done("Protocol detail tabs visible")

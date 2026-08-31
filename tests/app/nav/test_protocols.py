"""Protocols page navigation and detail tabs."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from automation.app_helpers.screenshot_helper import ScreenshotHelper
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
    label="Screenshot protocol detail tabs",
    order=20,
)
def test_protocol_detail_tabs(
    run_local_app: Page,
    protocol_name: str,
    screenshot_helper: ScreenshotHelper,
) -> None:
    """Open a protocol and click/screenshot each present detail tab."""
    log_step(f"Open protocol '{protocol_name}'")
    protocols = ProtocolsPage(run_local_app, shots=screenshot_helper)
    protocols.open(protocol_name)
    log_step("Click and screenshot each detail tab")
    protocols.capture_all_tabs()
    log_done("Protocol detail tabs captured")

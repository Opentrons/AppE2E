"""Protocol-list overflow actions (except Start setup — covered by protocol run tabs)."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages import ProtocolsPage


@pytest.mark.workflow(group="protocols", section="Protocol actions", label="Reanalyze", order=20)
def test_protocol_reanalyze(run_local_app: Page, protocol_name: str) -> None:
    """Trigger Reanalyze from the protocol card overflow menu."""
    log_step(f"Reanalyze '{protocol_name}' from overflow")
    ProtocolsPage(run_local_app).choose_overflow_action(protocol_name, "reanalyze")
    log_done("Reanalyze chosen")


@pytest.mark.workflow(
    group="protocols",
    section="Protocol actions",
    label="Send to Opentrons Flex",
    order=30,
)
def test_protocol_send_to_flex(run_local_app: Page, protocol_name: str) -> None:
    """Open Send to Flex from overflow, then dismiss the slideout."""
    page = run_local_app
    log_step(f"Send '{protocol_name}' to Flex from overflow")
    ProtocolsPage(page).choose_overflow_action(protocol_name, "send_to_flex")
    slideout = page.get_by_text("Send protocol to Opentrons Flex", exact=False).or_(
        page.get_by_role("heading", name="Send protocol")
    )
    expect(slideout.first).to_be_visible()
    page.keyboard.press("Escape")
    log_done("Send to Flex slideout opened and dismissed")


@pytest.mark.workflow(group="protocols", section="Protocol actions", label="Show in folder", order=40)
def test_protocol_show_in_folder(run_local_app: Page, protocol_name: str) -> None:
    """Choose Show in folder (OS file manager is not assertable here)."""
    log_step(f"Show '{protocol_name}' in folder from overflow")
    ProtocolsPage(run_local_app).choose_overflow_action(protocol_name, "show_in_folder")
    log_done("Show in folder chosen")


@pytest.mark.workflow(group="protocols", section="Protocol actions", label="Delete protocol", order=50)
def test_protocol_delete_cancel(run_local_app: Page, protocol_name: str) -> None:
    """Open Delete from overflow and cancel without removing the protocol."""
    page = run_local_app
    log_step(f"Open delete confirmation for '{protocol_name}'")
    ProtocolsPage(page).choose_overflow_action(protocol_name, "delete")
    cancel = page.get_by_role("button", name="Cancel", exact=True)
    expect(cancel).to_be_visible()
    cancel.click()
    log_done("Delete confirmation cancelled")

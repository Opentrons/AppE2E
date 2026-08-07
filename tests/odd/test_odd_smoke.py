"""ODD smoke covering TestRail C44415–C44420 (dashboard, protocols, pin, delete)."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from automation.app_helpers.screenshot_helper import ScreenshotHelper
from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages.odd import OddHomePage, OddProtocolsPage


@pytest.mark.odd
def test_odd_smoke_protocol_flows(run_odd_app: Page, screenshot_helper: ScreenshotHelper) -> None:
    """Exercise ODD dashboard, protocols list/sort, details, pin, and delete-bottom."""
    page = run_odd_app
    home = OddHomePage(page)
    protocols = OddProtocolsPage(page, shots=screenshot_helper)

    log_step("Assert ODD page is alive")
    home.expect_alive()
    screenshot_helper.capture("alive", "odd_attached")
    log_done(f"ODD alive — title={page.title()!r} url={page.url!r}")

    # --- C44419 Dashboard (ODD) ---
    log_step("C44419 Dashboard (ODD) — open robot dashboard")
    home.open_dashboard()
    home.expect_dashboard_content()
    screenshot_helper.capture("dashboard", "c44419")
    log_done("C44419 Dashboard visible (Run again or No recent runs)")

    # --- C44417 All Protocols (ODD) ---
    log_step("C44417 All Protocols (ODD) — open Protocols list")
    protocols.open()
    protocols.expect_protocol_list()
    screenshot_helper.capture("protocols", "c44417_list")
    log_done(f"C44417 Protocols list visible — {protocols.protocol_cards.count()} cards")

    # --- C44420 Protocol Sorting (ODD) ---
    log_step("C44420 Protocol Sorting (ODD) — Protocol Name / Last Run / Date Added")
    protocols.exercise_sorting()
    log_done("C44420 Sort headers exercised (snapshots under artifacts/odd/protocol_sorting/)")

    # --- C44418 Protocol Setup Details ---
    log_step("C44418 Protocol Setup Details — open first healthy protocol")
    protocols.open_first_healthy_protocol()
    log_done(f"Protocol details — url={page.url!r}")
    log_step("C44418 Protocol Setup Details — tabs + Start setup")
    protocols.expect_setup_details()
    log_done("C44418 Detail tabs and Start setup verified (snapshots under artifacts/odd/protocol_details/)")

    # --- C44416 Pin a Protocol (ODD) ---
    log_step("C44416 Pin a Protocol (ODD)")
    pinned = protocols.pin_protocol()
    protocols.back_to_protocols()
    if pinned:
        protocols.expect_pinned_section()
        screenshot_helper.capture("pin", "c44416_pinned")
        log_done("C44416 Protocol pinned (Pinned Protocols section visible)")
    else:
        screenshot_helper.capture("pin", "c44416_max_pins")
        log_done("C44416 Pin skipped — max pinned protocols already reached")

    # --- C44415 Delete a protocol (ODD) — bottom of list ---
    log_step("C44415 Delete a protocol (ODD) — open bottom healthy protocol")
    before = protocols.protocol_cards.count()
    protocols.open_last_healthy_protocol()
    screenshot_helper.capture("delete", "c44415_details")
    log_done(f"Opened bottom protocol — list had {before} unpinned cards")

    log_step("C44415 Delete a protocol (ODD) — confirm delete")
    protocols.delete_open_protocol()
    after = protocols.protocol_cards.count()
    screenshot_helper.capture("delete", "c44415_after")
    log_done(f"C44415 Protocol deleted — unpinned cards {before} → {after}")

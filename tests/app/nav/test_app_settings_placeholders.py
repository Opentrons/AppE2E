"""App Settings workflows not covered by the main tab smoke tests."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages import AppSettingsPage
from automation.app_pages.components import ToggleSwitch

ADVANCED_REQUIRED = "tests/app/nav/test_app_settings.py::test_advanced_tab"


@pytest.mark.workflow(group="app_settings", section="General", label="Change language and restore English", order=30)
@pytest.mark.skip(reason="TODO: app language round-trip has no page-object helper yet")
def test_app_language_round_trip() -> None:
    pass


@pytest.mark.workflow(
    group="app_settings",
    section="Advanced",
    label="Download protocol source file",
    order=40,
    requires=ADVANCED_REQUIRED,
)
def test_protocol_source_download_preference(run_local_app: Page) -> None:
    """Toggle include-protocol-source preference and restore the prior value."""
    settings = AppSettingsPage(run_local_app)
    log_step("Open App Settings > Advanced")
    settings.navigate()
    assert settings._open_tab("Advanced", "advanced")
    switch = ToggleSwitch(run_local_app, "include_protocol_source_in_run_download")
    expect(switch.locator).to_be_visible()
    original = switch.is_on()
    log_step(f"Toggle protocol source preference (was on={original})")
    if original:
        switch.turn_off()
        switch.turn_on()
    else:
        switch.turn_on()
        switch.turn_off()
    log_done("Protocol source preference toggled and restored")

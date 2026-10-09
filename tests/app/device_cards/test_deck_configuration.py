"""Deck Configuration tab on robot detail."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages import DeckConfigurationPage

ROBOT_DETAIL_REQUIRED = "tests/app/device_cards/test_devices_nav.py::test_robot_detail_from_devices_list"

EXPECTED_STANDARD_DECK_LABELS = {
    "Temperature",
    "Heater-Shaker",
    "Thermocycler",
    "Mag",
    "Absorbance",
    "Stage",
    "Stacker",
    "Waste",
}


@pytest.mark.workflow(
    group="devices",
    section="Deck Configuration",
    label="Review deck configuration",
    order=30,
    requires=ROBOT_DETAIL_REQUIRED,
    cases=(("C607", "Module & Fixture Labels"),),
)
def test_deck_configuration(
    run_local_app: Page,
    robot_name: str,
    device_details_tabs: bool,
) -> None:
    """Ensure the standard QA lab layout, clearing factory-default trash on A3 if needed."""
    if not device_details_tabs:
        pytest.skip("Deck Configuration tab requires the Device Details tabs layout.")

    log_step(f"Open Deck Configuration for '{robot_name}'")
    deck = DeckConfigurationPage(run_local_app, robot_name=robot_name)
    deck.open()

    labels = deck.configured_module_labels()
    log_step(f"Configured on deck ({len(labels)}): {labels or 'none'}")

    log_step("Ensure standard QA lab layout (clear Trash bin on A3 if present)")
    added = deck.configure_standard_deck()
    log_done(f"Deck configured — added {added or 'nothing (already complete)'}")

    after_labels = deck.configured_module_labels()
    after = set(after_labels)
    log_step(f"Configured after setup: {after_labels}")
    missing = EXPECTED_STANDARD_DECK_LABELS - after
    assert not missing, f"Missing configured labels after standard deck setup: {sorted(missing)}"
    assert after_labels.count("Stacker") == 2
    assert "Trash bin" not in after
    log_done("Standard deck layout configured")

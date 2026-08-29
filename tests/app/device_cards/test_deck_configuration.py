"""Deck Configuration tab on robot detail."""

from __future__ import annotations

import re
import time

import pytest
from playwright.sync_api import Page, expect

from automation.app_helpers.robot_connection import RobotConnection
from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages import DeckConfigurationPage

ROBOT_DETAIL_REQUIRED = "tests/app/device_cards/test_devices_nav.py::test_robot_detail_from_devices_list"

# D1 temperature is a single-slot module — safe remove/re-add without touching TC/stackers.
TEMPERATURE_OPTION = re.compile(r"Temperature Module GEN2")
TEMPERATURE_CUTOUT = "cutoutD1"
TEMPERATURE_FIXTURE = "temperatureModuleV2"


def _cutout_fixture(robot_connection: RobotConnection, cutout_id: str) -> str | None:
    payload = robot_connection("/deck_configuration")
    fixtures = payload.get("data", {}).get("cutoutFixtures", [])
    for entry in fixtures:
        if entry.get("cutoutId") == cutout_id:
            return entry.get("cutoutFixtureId")
    return None


def _wait_for_cutout_fixture(
    robot_connection: RobotConnection,
    cutout_id: str,
    expected: str,
    *,
    timeout_s: float = 15.0,
) -> str | None:
    deadline = time.monotonic() + timeout_s
    last: str | None = None
    while time.monotonic() < deadline:
        last = _cutout_fixture(robot_connection, cutout_id)
        if last == expected:
            return last
        time.sleep(0.5)
    return last


@pytest.mark.workflow(
    group="devices",
    section="Deck Configuration",
    label="Review deck configuration",
    order=30,
    requires=ROBOT_DETAIL_REQUIRED,
)
def test_deck_configuration(
    run_local_app: Page,
    robot_name: str,
    device_details_tabs: bool,
    robot_connection: RobotConnection,
) -> None:
    """Open Deck Configuration, remove/re-add Temperature on D1, validate vs robot."""
    if not device_details_tabs:
        pytest.skip("Deck Configuration tab requires the Device Details tabs layout.")

    log_step(f"Open Deck Configuration for '{robot_name}'")
    deck = DeckConfigurationPage(run_local_app, robot_name=robot_name)
    deck.open()

    labels = deck.configured_module_labels()
    log_step(f"Configured on deck ({len(labels)}): {labels or 'none'}")
    assert "Temperature" in labels, f"Expected Temperature on deck before exercise; got {labels}"

    before_fixture = _cutout_fixture(robot_connection, TEMPERATURE_CUTOUT)
    log_step(f"Robot {TEMPERATURE_CUTOUT} fixture before: {before_fixture}")
    assert before_fixture == TEMPERATURE_FIXTURE

    log_step("Remove Temperature from D1 (click configured module)")
    deck.remove_module_by_label("Temperature")
    expect(deck.slot("D1")).to_be_visible()
    assert "Temperature" not in deck.configured_module_labels()

    log_step("Re-add Temperature Module GEN2 to D1")
    deck.add_module_to_slot("D1", TEMPERATURE_OPTION)
    expect(deck.module_button("Temperature")).to_be_visible()

    after_labels = deck.configured_module_labels()
    log_step(f"Configured after re-add ({len(after_labels)}): {after_labels}")
    assert "Temperature" in after_labels

    after_fixture = _wait_for_cutout_fixture(
        robot_connection, TEMPERATURE_CUTOUT, TEMPERATURE_FIXTURE
    )
    log_step(f"Robot {TEMPERATURE_CUTOUT} fixture after: {after_fixture}")
    assert after_fixture == TEMPERATURE_FIXTURE
    log_done("Deck Configuration remove/re-add validated against robot")

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from automation.app_helpers.robot_connection import (
    DEVICE_RESET_READY_TIMEOUT_S,
    RobotConnection,
)
from automation.app_helpers.test_progress import log_done, log_step, run_timed
from automation.app_pages import DevicesPage, RobotSettingsPage
from automation.app_pages.LPC_Helpers.calibration_helper import CalibrationHelper

# Gripper calibration and deck configuration are still manual (see Flex setup prompt).

"""
Device reset first
C44408	HS Calibration
C44407	TD Calibration
C44406	TC Calibration
C44404	Devices > Robot > Protocol Run > Module controls
"""


@pytest.mark.workflow(
    group="run_setup",
    section="Calibration",
    label="Reset calibration data",
    order=60,
    cases=(("T69755", "Device Reset"),),
)
def test_device_reset(
    run_local_app: Page,
    robot_name: str,
    robot_connection: RobotConnection,
) -> None:
    """Clear Flex calibration / run data via Device Reset and wait for restart.

    Devices > Robot > Robot Settings > Advanced > Choose reset settings:
    pipette / gripper / module calibration, protocol run history, labware offsets.
    Confirms restart, then waits for robot-server health (up to ~20 minutes).
    """
    page = run_local_app
    settings = RobotSettingsPage(page, robot_name=robot_name)
    run_timed(f"Open Robot Settings for '{robot_name}'", settings.navigate)
    run_timed(
        "Device Reset: clear calibration, run history, and labware offsets",
        settings.reset_flex_calibration_data,
    )
    run_timed(
        f"Wait for robot ready (up to {DEVICE_RESET_READY_TIMEOUT_S / 60:.0f} min)",
        robot_connection.wait_for_ready_after_reset,
    )
    devices = DevicesPage(page, robot_name=robot_name)
    run_timed(f"Re-open robot detail for '{robot_name}'", devices.navigate)


@pytest.mark.workflow(group="run_setup", section="Calibration", label="Review calibration status", order=70)
def test_calibration_flow(run_local_app: Page, robot_name: str) -> None:
    """List pipette, gripper, and module calibration status on Robot Settings."""
    log_step(f"Open Robot Settings Calibration for '{robot_name}'")
    calibration = CalibrationHelper(run_local_app, robot_name=robot_name)
    calibration.get_calibration_page()

    log_step("List calibration status for pipettes, grippers, and modules")
    items = calibration.list_calibration_status()
    for item in items:
        if item.is_calibrated:
            log_step(f"{item.category}: {item.label} ({item.serial}) - {item.state_label} ({item.status})")
        else:
            log_step(f"{item.category}: {item.label} ({item.serial}) - {item.state_label}")

    if calibration.is_calibration_needed():
        log_done(f"Calibration needed on at least one instrument ({robot_name})")
    else:
        log_done(f"All calibratable instruments are calibrated ({robot_name})")


@pytest.mark.workflow(
    group="run_setup",
    section="Calibration",
    label="Open calibration overflow menus",
    order=80,
)
def test_calibration_overflow_menu(run_local_app: Page, robot_name: str) -> None:
    """Open overflow menu for each instrument that shows Not calibrated."""
    log_step(f"Open Robot Settings Calibration for '{robot_name}'")
    calibration = CalibrationHelper(run_local_app, robot_name=robot_name)
    calibration.get_calibration_page()

    log_step("Open overflow menus for uncalibrated instruments")
    # Pick categories as needed, e.g. categories=["pipette", "gripper"]
    uncalibrated = calibration.verify_overflow_menus()
    if not uncalibrated:
        pytest.skip("No uncalibrated instruments on Robot Settings > Calibration")

    log_done(f"Overflow menus verified for uncalibrated instruments ({robot_name})")


@pytest.mark.workflow(
    group="run_setup",
    section="Calibration",
    label="Calibrate 96-channel pipette",
    order=90,
)
def test_96_channel_calibration(run_local_app: Page, robot_name: str) -> None:
    """Run the full Flex 96-channel pipette calibration wizard."""
    log_step(f"Open Robot Settings Calibration for '{robot_name}'")
    calibration = CalibrationHelper(run_local_app, robot_name=robot_name)
    calibration.get_calibration_page()

    log_step("Run 96-channel calibration (attach probe when prompted)")
    item = calibration.run_96_channel_calibration()
    log_done(f"{calibration.last_success_message} - {item.label} ({item.serial})")


@pytest.mark.workflow(
    group="run_setup",
    section="Calibration",
    label="Calibrate Heater-Shaker",
    order=100,
    cases=(("C44408", "HS Calibration"),),
)
def test_heater_shaker_calibration(run_local_app: Page, robot_name: str) -> None:
    """Run the full Heater-Shaker Module Wizard calibration from Robot Settings.

    Requires an attached Heater-Shaker Module GEN1 with deck location configured,
    a calibrated pipette, calibration adapter + probe ready, and the module cool.

    Steps:
    - Calibrate module from the Module Calibration overflow menu
    - Start setup (firmware check runs first and may need Install update)
    - Confirm location
    - Verify the in-motion screen, no clicking
    - Confirm placement (secure the adapter with the T10 Torx screw first)
    - Verify the in-motion screen, no clicking
    - Begin calibration (attach the probe first)
    - Verify probing runs, no clicking
    - Complete calibration (remove the probe first)
    - Finish on the "successfully set up" screen
    """
    log_step(f"Open Robot Settings Calibration for '{robot_name}'")
    calibration = CalibrationHelper(run_local_app, robot_name=robot_name)
    calibration.get_calibration_page()

    log_step("Run Heater-Shaker calibration (adapter + probe when prompted)")
    item = calibration.run_heater_shaker_calibration()
    log_done(f"{calibration.last_success_message} - {item.label} ({item.serial})")


@pytest.mark.workflow(
    group="run_setup",
    section="Calibration",
    label="Calibrate Temperature Module",
    order=110,
    cases=(("C44407", "TD Calibration"),),
)
def test_temperature_module_calibration(run_local_app: Page, robot_name: str) -> None:
    """Run the full Temperature Module Wizard calibration from Robot Settings.

    Requires an attached Temperature Module GEN2 with deck location configured,
    a calibrated pipette, calibration adapter + probe ready, and the module cool.

    Steps:
    - Calibrate module from the Module Calibration overflow menu
    - Start setup (firmware check runs first and may need Install update)
    - Confirm location
    - Verify the in-motion screen, no clicking
    - Confirm placement (place the adapter flush on the module first)
    - Verify the in-motion screen, no clicking
    - Begin calibration (attach the probe first)
    - Verify probing runs, no clicking
    - Complete calibration (remove the probe first)
    - Finish on the "successfully set up" screen
    """
    log_step(f"Open Robot Settings Calibration for '{robot_name}'")
    calibration = CalibrationHelper(run_local_app, robot_name=robot_name)
    calibration.get_calibration_page()

    log_step("Run Temperature Module calibration (adapter + probe when prompted)")
    item = calibration.run_temperature_module_calibration()
    log_done(f"{calibration.last_success_message} - {item.label} ({item.serial})")


@pytest.mark.workflow(
    group="run_setup",
    section="Calibration",
    label="Calibrate Thermocycler",
    order=120,
    cases=(("C44406", "TC Calibration"),),
)
def test_thermocycler_calibration(run_local_app: Page, robot_name: str) -> None:
    """Run the full Thermocycler Module Wizard calibration from Robot Settings.

    Requires an attached Thermocycler Module GEN2 with deck location configured,
    a calibrated pipette, calibration adapter + probe ready, and the module cool.
    Open the Thermocycler lid before Confirm placement.

    Steps:
    - Calibrate module from the Module Calibration overflow menu
    - Start setup (firmware check runs first and may need Install update)
    - Confirm location
    - Verify the in-motion screen, no clicking
    - Confirm placement (lid open, adapter flush on the module first)
    - Verify the in-motion screen, no clicking
    - Begin calibration (attach the probe first)
    - Verify probing runs, no clicking
    - Complete calibration (remove the probe first)
    - Finish on the "successfully set up" screen
    """
    log_step(f"Open Robot Settings Calibration for '{robot_name}'")
    calibration = CalibrationHelper(run_local_app, robot_name=robot_name)
    calibration.get_calibration_page()

    log_step("Run Thermocycler calibration (adapter + probe when prompted)")
    item = calibration.run_thermocycler_calibration()
    log_done(f"{calibration.last_success_message} - {item.label} ({item.serial})")

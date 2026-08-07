from __future__ import annotations

import pytest
from playwright.sync_api import Page

from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages.LPC_Helpers.calibration_helper import CalibrationHelper

# TODO: Add a strong recommendation to do gripper calibration before using this. Since it is unautomatable
# TODO: Add a deck configuration step because that ain't going in here

"""
C44408	HS Calibration
C44407	TD Calibration
C44406	TC Calibration
C44404	Devices > Robot > Protocol Run > Module controls
"""


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


def test_96_channel_calibration(run_local_app: Page, robot_name: str) -> None:
    """Run the full Flex 96-channel pipette calibration wizard."""
    log_step(f"Open Robot Settings Calibration for '{robot_name}'")
    calibration = CalibrationHelper(run_local_app, robot_name=robot_name)
    calibration.get_calibration_page()

    log_step("Run 96-channel calibration (attach probe when prompted)")
    item = calibration.run_96_channel_calibration()
    log_done(f"{calibration.last_success_message} - {item.label} ({item.serial})")


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

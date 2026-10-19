"""Robot Settings > File manager workflows."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages import FileManagerPage

ROBOT_DETAIL_REQUIRED = "tests/app/device_cards/test_devices_nav.py::test_robot_detail_from_devices_list"


@pytest.mark.workflow(
    group="robot_settings",
    section="File manager",
    label="File capacity",
    order=40,
    requires=ROBOT_DETAIL_REQUIRED,
)
def test_file_capacity(run_local_app: Page, robot_name: str) -> None:
    """Open File manager and read the storage meter."""
    log_step(f"Open File manager storage for '{robot_name}'")
    files = FileManagerPage(run_local_app, robot_name=robot_name)
    files.open()
    capacity = files.capacity()
    log_step(
        f"File capacity: {capacity.percent_used}% used, "
        f"{capacity.percent_available}% available ({capacity.value_text or 'n/a'})"
    )
    assert 0 <= capacity.percent_used <= 100
    assert capacity.percent_used + capacity.percent_available == 100
    log_done("File capacity read")


@pytest.mark.workflow(
    group="robot_settings",
    section="File manager",
    label="Review protocol run records",
    order=50,
    requires=ROBOT_DETAIL_REQUIRED,
)
def test_protocol_run_records(run_local_app: Page, robot_name: str) -> None:
    """List protocol run records and expand the first one when present."""
    log_step(f"Open File manager run records for '{robot_name}'")
    files = FileManagerPage(run_local_app, robot_name=robot_name)
    files.open()
    records = files.run_records()
    rows = records.rows()
    log_step(f"Found {len(rows)} protocol run record(s)")
    if not rows:
        log_done("No protocol run records present")
        return
    records.expand(0)
    file_map = records.files(0)
    log_step(f"First record files: {file_map or 'none'}")
    log_done("Protocol run records reviewed")


@pytest.mark.workflow(
    group="robot_settings",
    section="File manager",
    label="Download diagnostic files",
    order=60,
    requires=ROBOT_DETAIL_REQUIRED,
)
def test_diagnostic_files(run_local_app: Page, robot_name: str) -> None:
    """Select a Diagnostic Files filetype and click Download selected."""
    log_step(f"Open File manager diagnostics for '{robot_name}'")
    files = FileManagerPage(run_local_app, robot_name=robot_name)
    files.open()
    diagnostics = files.diagnostics()
    rows = diagnostics.rows()
    log_step(f"Diagnostic rows: {rows or 'none'}")
    if not rows:
        log_done("No diagnostic files present")
        return
    target = diagnostics.TROUBLESHOOTING_LOGS if diagnostics.TROUBLESHOOTING_LOGS in rows else rows[0]
    log_step(f"Select '{target}' and Download selected")
    zip_path = files.complete_diagnostic_download(diagnostics, target)
    log_done(f"Downloaded diagnostic file '{target}' → {zip_path.name}")


@pytest.mark.workflow(
    group="robot_settings",
    section="File manager",
    label="Download calibration logs",
    order=70,
    requires=ROBOT_DETAIL_REQUIRED,
)
def test_download_calibration_logs(run_local_app: Page, robot_name: str) -> None:
    """Select Calibration Logs and click Download selected when listed."""
    log_step(f"Open File manager calibration logs for '{robot_name}'")
    files = FileManagerPage(run_local_app, robot_name=robot_name)
    files.open()
    diagnostics = files.diagnostics()
    rows = diagnostics.rows()
    calibration_rows = [row for row in rows if "calibration" in row.lower()]
    log_step(f"Calibration-related rows: {calibration_rows or 'none'}")
    if not calibration_rows:
        pytest.skip("No calibration log rows listed in File manager diagnostics.")
    target = calibration_rows[0]
    log_step(f"Select '{target}' and Download selected")
    zip_path = files.complete_diagnostic_download(diagnostics, target)
    log_done(f"Downloaded '{target}' → {zip_path.name}")

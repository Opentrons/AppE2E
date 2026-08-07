"""Device reset and calibration flow.

Placeholder for a fuller reset → recalibrate scenario. Kept separate from
Robot Settings Advanced checks so it can grow without blocking that suite.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from automation.app_helpers.test_progress import log_done, log_step


@pytest.mark.skip(reason="TODO: implement device reset + calibrate flow")
def test_device_reset_and_calibrate(run_local_app: Page, robot_name: str) -> None:
    """Reset device settings and recalibrate — flesh out later."""
    log_step(f"Device reset and calibrate for '{robot_name}'")
    _ = run_local_app  # page reserved for upcoming steps
    log_done("Device reset and calibrate OK")

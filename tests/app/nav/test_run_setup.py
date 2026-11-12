"""Protocol run setup steps on the Setup tab."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from automation.app_helpers.protocol_run_target import ProtocolRunTarget
from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages import (
    ChooseRobotToRunProtocolSlideout,
    DevicesPage,
    ProtocolRunPage,
    ProtocolsPage,
    RunSetupPage,
)
from automation.app_pages_crs import SignRunPage

PROTOCOL_RUN_TABS_REQUIRED = "tests/app/nav/test_protocol_run_tabs.py::test_protocol_run_tabs"
CAMERA_SETUP_REQUIRED = "tests/app/nav/test_run_setup.py::test_run_setup_step[Camera]"
CANCEL_RUN_AFTER_SETUP = "tests/app/nav/test_run_setup.py::test_cancel_run_after_setup"


def _open_existing_run_if_present(page: Page, robot_name: str) -> bool:
    """Open the robot's current run via Devices → Go to Run when one exists."""
    if "protocol-runs/" in page.url:
        return True
    devices = DevicesPage(page, robot_name=robot_name)
    if not devices.open_current_run_if_present():
        return False
    ProtocolRunPage(page, robot_name=robot_name).wait_until_open()
    return True


def _open_run_setup(page: Page, protocol_name: str, robot_name: str) -> RunSetupPage:
    """Create a protocol run (if needed) and land on the Setup tab.

    Reuses an already-current run (Devices → Go to Run) instead of opening Choose
    robot, which hides busy robots and cannot create a second run.
    """
    run_page = ProtocolRunPage(page, robot_name=robot_name)
    if "protocol-runs/" not in page.url:
        log_step(f"Look for an open run on '{robot_name}'")
        if _open_existing_run_if_present(page, robot_name):
            log_done("Reusing the current protocol run")
        else:
            target = ProtocolRunTarget(protocol_name=protocol_name, robot_name=robot_name)
            log_step(f"Start setup for '{protocol_name}'")
            ProtocolsPage(page).start_setup(protocol_name)
            log_step(f"Select robot '{robot_name}' and proceed to run")
            ChooseRobotToRunProtocolSlideout(page).start_run(target)
            run_page.wait_until_open()
    else:
        run_page.wait_until_open()
    run_page.open_tab("Setup", "setup")
    # Setup accordions replace the loading screen only after analysis finishes
    # and the header action changes from "Analyzing on robot" to "Start run".
    log_step("Wait for protocol analysis to finish")
    run_page.wait_until_analysis_complete()
    log_done("Start run is available")
    return RunSetupPage(page)


@pytest.mark.parametrize(
    "step",
    [
        pytest.param(
            "Instruments",
            marks=pytest.mark.workflow(
                group="run_setup",
                section="Setup",
                label="Instruments",
                order=10,
                requires=PROTOCOL_RUN_TABS_REQUIRED,
            ),
        ),
        pytest.param(
            "Deck Hardware",
            marks=pytest.mark.workflow(
                group="run_setup",
                section="Setup",
                label="Deck Hardware",
                order=20,
                requires=PROTOCOL_RUN_TABS_REQUIRED,
                cases=(("C607", "Module & Fixture Labels"),),
            ),
        ),
        pytest.param(
            "Labware Offsets",
            marks=pytest.mark.workflow(
                group="run_setup",
                section="Setup",
                label="Labware Offsets",
                order=30,
                requires=PROTOCOL_RUN_TABS_REQUIRED,
            ),
        ),
        pytest.param(
            "Labware & Liquids",
            marks=pytest.mark.workflow(
                group="run_setup",
                section="Setup",
                label="Labware & Liquids",
                order=40,
                requires=PROTOCOL_RUN_TABS_REQUIRED,
            ),
        ),
        pytest.param(
            "Camera",
            marks=pytest.mark.workflow(
                group="run_setup",
                section="Setup",
                label="Camera",
                order=50,
                requires=PROTOCOL_RUN_TABS_REQUIRED,
            ),
        ),
    ],
)
def test_run_setup_step(
    run_local_app: Page,
    protocol_name: str,
    robot_name: str,
    step: str,
) -> None:
    """Expand one Setup step and log its status chip when present."""
    page = run_local_app
    setup = _open_run_setup(page, protocol_name, robot_name)
    log_step(f"Expand setup step '{step}'")
    setup.expand(step)
    status = setup.status(step)
    log_step(f"Step '{step}' status: {status or 'none'}")
    log_done(f"Setup step '{step}' reviewed")


@pytest.mark.workflow(
    group="run_setup",
    section="Cleanup",
    label="Cancel protocol after Camera",
    order=60,
    requires=CAMERA_SETUP_REQUIRED,
)
def test_cancel_run_after_setup(run_local_app: Page, robot_name: str) -> None:
    """Cancel the protocol run left open after Setup → Camera (run_setup cleanup).

    Calibration does not depend on this test; those flows cancel an open run
    themselves when one is present. This stays as the Protocol setup group's
    cleanup step after Camera.

    If the session is not already on the run page (Camera failed, or suite
    resumed on Devices), open it via Go to Run before canceling.
    """
    page = run_local_app
    run_page = ProtocolRunPage(page, robot_name=robot_name)
    if "protocol-runs/" not in page.url:
        log_step(f"Open current run on '{robot_name}' via Go to Run")
        if not _open_existing_run_if_present(page, robot_name):
            raise AssertionError(
                f"No current protocol run on '{robot_name}' to cancel "
                "(Go to Run was not available on Devices)"
            )
        log_done("Protocol run page opened from Devices")
    else:
        run_page.wait_until_open()
    log_step("Cancel the protocol run left open after Setup → Camera")
    if not run_page.cancel_active_run():
        raise AssertionError("Cancel run was not available on the protocol run header")
    # CRS with require-signoff: closeCurrentRun opens Sign protocol run before dismiss.
    SignRunPage(page).complete_if_required(timeout_ms=60_000)
    log_done("Protocol run canceled")

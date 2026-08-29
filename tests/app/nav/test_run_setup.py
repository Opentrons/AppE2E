"""Protocol run setup steps on the Setup tab."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from automation.app_helpers.protocol_run_target import ProtocolRunTarget
from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages import (
    ChooseRobotToRunProtocolSlideout,
    ProtocolRunPage,
    ProtocolsPage,
    RunSetupPage,
)

PROTOCOL_RUN_TABS_REQUIRED = "tests/app/nav/test_protocol_run_tabs.py::test_protocol_run_tabs"


def _open_run_setup(page: Page, protocol_name: str, robot_name: str) -> RunSetupPage:
    """Create a protocol run (if needed) and land on the Setup tab."""
    run_page = ProtocolRunPage(page)
    if "protocol-runs/" not in page.url:
        target = ProtocolRunTarget(protocol_name=protocol_name, robot_name=robot_name)
        log_step(f"Start setup for '{protocol_name}'")
        ProtocolsPage(page).start_setup(protocol_name)
        log_step(f"Select robot '{robot_name}' and proceed to run")
        ChooseRobotToRunProtocolSlideout(page).start_run(target)
        run_page.wait_until_open()
    else:
        run_page.wait_until_open()
    run_page.open_tab("Setup", "setup")
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

"""Clear an open desktop protocol run so calibration / deck edits are not blocked."""

from __future__ import annotations

from playwright.sync_api import Page

from automation.app_helpers.crs_accounts import CrsAccount
from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages import DevicesPage, ProtocolRunPage
from automation.app_pages_crs import SignRunPage


def cancel_open_protocol_run_if_present(
    page: Page,
    *,
    robot_name: str,
    account: CrsAccount | None = None,
) -> bool:
    """Cancel the robot's current protocol run when one is open.

    On Compliance Ready robots with sign-off required, canceling a current run
    opens Sign protocol run before dismiss — complete that signature too.

    Returns True when a run was canceled, False when none was open (or Cancel
    was not available because the run is already terminal).
    """
    run_page = ProtocolRunPage(page, robot_name=robot_name)
    if "protocol-runs/" not in page.url:
        log_step(f"Check for an open protocol run on '{robot_name}'")
        if not DevicesPage(page, robot_name=robot_name).open_current_run_if_present():
            log_done("No open protocol run")
            # A previously canceled run may still need a signature on Devices.
            SignRunPage(page).complete_if_required(account, timeout_ms=3_000)
            return False
        log_done("Opened current protocol run")
    else:
        run_page.wait_until_open()

    log_step("Cancel the open protocol run")
    if not run_page.cancel_active_run():
        # Already terminal — still may need Sign protocol run before dismiss.
        if SignRunPage(page).complete_if_required(account, timeout_ms=5_000):
            log_done("Signed terminal protocol run")
            return True
        log_done("Cancel run not available (robot already idle)")
        return False

    SignRunPage(page).complete_if_required(account, timeout_ms=60_000)
    log_done("Protocol run canceled")
    return True

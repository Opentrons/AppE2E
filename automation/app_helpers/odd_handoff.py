"""Desktop steps that leave the robot idle before Flex ODD tests attach.

A full app suite ends on a protocol run. Starting another Playwright from that
same process fails, and the touchscreen stays on that run. Cancel it, open the
robot, and turn ODD developer tools back on before the ODD session connects.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx
from playwright.sync_api import Page

import open_app
from automation.app_helpers.app_readiness import dismiss_blocking_ui
from automation.app_helpers.protocol_run_target import ProtocolRunTarget
from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages import (
    ChooseRobotToRunProtocolSlideout,
    DevicesPage,
    ProtocolRunPage,
    ProtocolsPage,
)

_ROBOT_PORT = 31950
_DEVTOOLS_PROTOCOL = "Enable ODD developer tools"
_DEVTOOLS_PATH = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "protocols" / "enable_odd_devtools.py"
)
_TERMINAL_STATUSES = {"stopped", "succeeded", "failed"}


def prepare_desktop_for_odd(page: Page, *, robot_name: str, robot_ip: str) -> None:
    """Cancel run, open the robot, and make the ODD debug port available."""
    robot_name = _robot_name_from_run(page) or robot_name
    log_step(f"Hand off {robot_name} from the desktop app to ODD tests")
    dismiss_blocking_ui(page)
    _open_current_run(page, robot_name=robot_name, robot_ip=robot_ip)
    if "protocol-runs/" in page.url and ProtocolRunPage(page, robot_name=robot_name).cancel_active_run():
        log_done("Canceled the desktop run")
    _wait_until_robot_idle(robot_ip)
    log_step(f"Open {robot_name}")
    DevicesPage(page, robot_name=robot_name).navigate()
    log_done(f"{robot_name} is open")
    _ensure_odd_devtools(page, robot_name=robot_name, robot_ip=robot_ip)


def _robot_name_from_run(page: Page) -> str | None:
    """Return the robot name already open on a protocol-run URL."""
    match = re.search(r"#/devices/([^/]+)/protocol-runs/", page.url)
    if match is None:
        return None
    name = unquote(match.group(1)).strip()
    return name or None


def _open_current_run(page: Page, *, robot_name: str, robot_ip: str) -> None:
    """Open the current protocol run when the desktop is not already on it."""
    if "protocol-runs/" in page.url:
        return
    try:
        current = _current_run(robot_ip)
    except httpx.HTTPError as error:
        log_step(f"Could not read the current run from {robot_ip}: {error}")
        return
    if current is None:
        return
    run_id = str(current.get("id") or "").strip()
    if not run_id:
        return
    log_step(f"Open the current run on {robot_name}")
    base = page.url.split("#", 1)[0]
    page.goto(f"{base}#/devices/{robot_name}/protocol-runs/{run_id}")
    ProtocolRunPage(page, robot_name=robot_name).wait_until_open()


def _ensure_odd_devtools(page: Page, *, robot_name: str, robot_ip: str) -> None:
    """Run the devtools protocol when the touchscreen debug port is down."""
    if open_app.odd_cdp_is_ready(robot_ip):
        log_done("ODD developer tools are already on")
        return
    log_step("ODD developer tools are off; run Enable ODD developer tools")
    protocols = ProtocolsPage(page)
    protocols.ensure_protocol_imported(_DEVTOOLS_PROTOCOL, _DEVTOOLS_PATH)
    protocols.start_setup(_DEVTOOLS_PROTOCOL)
    ChooseRobotToRunProtocolSlideout(page).start_run(
        ProtocolRunTarget(protocol_name=_DEVTOOLS_PROTOCOL, robot_name=robot_name)
    )
    run = ProtocolRunPage(page, robot_name=robot_name)
    run.wait_until_open()
    run.wait_until_analysis_complete()
    outcome = run.start_run_and_wait_until_finished()
    if outcome.lower() != "completed":
        raise AssertionError(f"Enable ODD developer tools finished as {outcome!r}")
    log_done("Enable ODD developer tools completed")
    _wait_until_robot_idle(robot_ip)
    open_app.wait_for_odd_cdp(robot_ip, timeout=120)
    log_done("ODD developer tools are on")


def _runs(robot_ip: str) -> list[dict[str, Any]]:
    """Return recent runs from robot-server."""
    url = f"http://{robot_ip}:{_ROBOT_PORT}/runs"
    with httpx.Client(headers={"Opentrons-Version": "*"}, timeout=15) as client:
        response = client.get(url, params={"pageLength": 20})
        response.raise_for_status()
        payload = response.json()
    data = payload.get("data", [])
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _current_run(robot_ip: str) -> dict[str, Any] | None:
    """Return the robot's current run, if one is still open."""
    for run in _runs(robot_ip):
        if run.get("current") is True:
            return run
    return None


def _dismiss_run(robot_ip: str, run_id: str) -> None:
    """Mark a finished run as not current so the touchscreen can leave it."""
    url = f"http://{robot_ip}:{_ROBOT_PORT}/runs/{run_id}"
    with httpx.Client(headers={"Opentrons-Version": "*"}, timeout=30) as client:
        response = client.patch(url, json={"data": {"current": False}})
        response.raise_for_status()


def _wait_until_robot_idle(robot_ip: str, *, timeout_s: float = 180) -> None:
    """Wait until robot-server has no current run, dismissing a finished one."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            current = _current_run(robot_ip)
        except httpx.HTTPError:
            time.sleep(2)
            continue
        if current is None:
            log_done("Robot has no current run")
            return
        status = str(current.get("status") or "")
        run_id = str(current.get("id") or "")
        if status in _TERMINAL_STATUSES and run_id:
            try:
                _dismiss_run(robot_ip, run_id)
            except httpx.HTTPError:
                pass
        time.sleep(2)
    raise TimeoutError(f"Robot {robot_ip} still has a current run after {timeout_s:.0f}s")

"""Helpers for local Flex dev robot (robot-server + localhost discovery)."""

from __future__ import annotations

import time

import httpx
from playwright.sync_api import Page, expect

from automation.app_helpers.app_readiness import click_when_ui_ready, dismiss_blocking_ui
from automation.app_helpers.left_nav import link
from automation.app_helpers.list_scroll import scroll_until_visible
from automation.app_helpers.locator_helpers import exact_text

LOCALHOST = "localhost"
ROBOT_SERVER_PORT = 31950
HEALTH_HEADERS = {"Opentrons-Version": "*"}


def wait_for_robot_server(
    *,
    host: str = LOCALHOST,
    port: int = ROBOT_SERVER_PORT,
    timeout: float = 180.0,
) -> None:
    """Poll GET /health until the dev robot-server responds."""
    url = f"http://{host}:{port}/health"
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with httpx.Client(headers=HEALTH_HEADERS, timeout=3.0) as client:
                response = client.get(url)
                if response.status_code == 200:
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(1.0)
    raise TimeoutError(
        f"Robot server not ready at {url} after {timeout}s" + (f" (last error: {last_error})" if last_error else "")
    )


def ensure_localhost_robot_discovered(
    page: Page,
    *,
    robot_name: str,
    host: str = LOCALHOST,
    timeout: float = 90_000,
) -> None:
    """Add localhost to manual discovery if the dev robot card is not visible yet."""
    ensure_robot_ip_discovered(page, robot_name=robot_name, host=host, timeout=timeout)


def ensure_robot_ip_discovered(
    page: Page,
    *,
    robot_name: str,
    host: str,
    timeout: float = 90_000,
    force: bool = False,
) -> None:
    """Add a robot IP to manual discovery and wait for its device card."""
    robot_card = page.get_by_test_id(f"RobotCard_{robot_name}_overflowMenu")
    if not force and robot_card.count() > 0 and robot_card.first.is_visible():
        return

    settings_link = (
        page.get_by_role("button", name=exact_text("App Settings"))
        .or_(page.get_by_test_id("Navbar_settingsLink"))
        .first
    )
    expect(settings_link).to_be_visible(timeout=60_000)
    click_when_ui_ready(page, settings_link)
    page.get_by_role("button", name="Set up connection").click()
    expect(page.get_by_text(exact_text("Add IP Address or Hostname"))).to_be_visible()

    if page.get_by_test_id("ip-hostname").filter(has_text=host).count() == 0:
        page.get_by_test_id("manual-ip-hostname-input").fill(host)
        page.get_by_role("button", name="Add").click()

    done = page.get_by_role("button", name=exact_text("Done"))
    if done.count() > 0 and done.first.is_visible():
        done.first.click()
    else:
        page.keyboard.press("Escape")

    dismiss_blocking_ui(page)
    click_when_ui_ready(page, link(page, "Devices"))
    scroll_until_visible(
        page,
        robot_card.first,
        not_found_message=f"Robot {robot_name!r} did not appear on Devices after adding {host}",
    )

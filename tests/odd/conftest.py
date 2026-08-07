"""Fixtures for Flex ODD (On-Device Display) Playwright tests over remote CDP."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from playwright.sync_api import Browser, Page, Playwright

import open_app
from automation.app_helpers.artifacts import ODD_ARTIFACTS_DIR
from automation.app_helpers.robot_connection import resolve_robot_ip
from automation.app_helpers.screenshot_helper import ScreenshotHelper
from automation.app_helpers.test_progress import log_step


@pytest.fixture(scope="session")
def robot_ip(request: pytest.FixtureRequest) -> str:
    """Resolved robot IP used for ODD CDP attach."""
    cli_ip = request.config.getoption("--robot-ip")
    ip = resolve_robot_ip(cli_ip=cli_ip)
    log_step(f"Robot IP: {ip}")
    return ip


@pytest.fixture(scope="session")
def run_odd_app(request: pytest.FixtureRequest, robot_ip: str) -> Generator[Page, None, None]:
    """Attach to the Flex ODD over CDP (``--robot-ip`` / ``ROBOT_IP`` / ``CDP_HOST``, port 9223)."""
    log_step(f"Attaching to Flex ODD over CDP at {robot_ip} (Developer Tools must be enabled)")
    playwright: Playwright | None = None
    browser: Browser | None = None

    playwright, browser, page = open_app.connect_odd_playwright(host=robot_ip)
    request.session.playwright_debug_page = page
    yield page

    if browser is not None:
        try:
            browser.close()
        except Exception:
            pass
    if playwright is not None:
        playwright.stop()


@pytest.fixture(scope="session")
def screenshot_helper(run_odd_app: Page) -> ScreenshotHelper:
    """Session-scoped helper for saving PNGs under ``artifacts/odd/<section>/``."""
    return ScreenshotHelper(run_odd_app, output_dir=ODD_ARTIFACTS_DIR)
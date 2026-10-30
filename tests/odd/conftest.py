"""Fixtures for Flex ODD (On-Device Display) Playwright tests over remote CDP."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Browser, Page, Playwright
from pytest_html import extras as html_extras

import open_app
from automation.app_helpers.reporting import (
    finalize_workflow_video,
    path_relative_to_report,
    slugify_nodeid,
    start_test_recording,
    stop_test_recording,
    take_workflow_segments,
    video_embed_html,
)
from automation.app_helpers.robot_connection import resolve_robot_ip
from automation.app_helpers.robot_profiles import DEFAULT_HARDWARE_ROBOT_NAME
from automation.app_helpers.screencast_recorder import CDP_HTTP_ATTR
from automation.app_helpers.test_progress import log_path, log_step
from run_config import is_headed_run


@pytest.fixture(scope="session")
def robot_ip(request: pytest.FixtureRequest) -> str:
    """Resolved robot IP used for ODD CDP attach."""
    cli_ip = request.config.getoption("--robot-ip")
    ip = resolve_robot_ip(cli_ip=cli_ip)
    log_step(f"Robot IP: {ip}")
    return ip


def _robot_display_name(request: pytest.FixtureRequest) -> str:
    """Robot name for the desktop handoff. ``--robot-name`` is a root pytest option."""
    env_name = os.environ.get("ROBOT_NAME", "").strip()
    if env_name:
        return env_name
    try:
        cli_name = request.config.getoption("--robot-name")
    except ValueError:
        cli_name = None
    if cli_name:
        return str(cli_name).strip()
    return DEFAULT_HARDWARE_ROBOT_NAME


def _desktop_page(request: pytest.FixtureRequest) -> Page | None:
    """Return the desktop app page when this session already launched it."""
    page = getattr(request.session, "playwright_debug_page", None)
    if not isinstance(page, Page):
        return None
    try:
        if page.is_closed():
            return None
        browser = page.context.browser
    except Exception:
        return None
    cdp_url = str(getattr(browser, CDP_HTTP_ATTR, "") or "")
    if f":{open_app.ODD_CDP_PORT}" in cdp_url:
        return None
    return page


@pytest.fixture(scope="session")
def run_odd_app(request: pytest.FixtureRequest, robot_ip: str) -> Generator[Page, None, None]:
    """Attach to the Flex ODD over CDP (``--robot-ip`` / ``ROBOT_IP`` / ``CDP_HOST``, port 9223).

    When the desktop app is already open in this pytest session, cancel its run,
    return to the robot, and re-enable ODD developer tools before attaching.
    """
    desktop = _desktop_page(request)
    if desktop is not None:
        from automation.app_helpers.odd_handoff import prepare_desktop_for_odd

        prepare_desktop_for_odd(
            desktop,
            robot_name=_robot_display_name(request),
            robot_ip=robot_ip,
        )

    log_step(f"Attaching to Flex ODD over CDP at {robot_ip} (Developer Tools must be enabled)")
    playwright: Playwright | None = None
    browser: Browser | None = None

    playwright, browser, page = open_app.connect_odd_playwright(host=robot_ip)
    from automation.app_pages.odd.odd_shell import OddShell

    OddShell(page).dismiss_canceled_run_if_present(wait_ms=3_000)
    request.session.playwright_debug_page = page
    yield page

    if browser is not None:
        try:
            browser.close()
        except Exception:
            pass
    if playwright is not None:
        open_app.release_playwright()


@pytest.fixture(autouse=True)
def _record_odd_video(request: pytest.FixtureRequest) -> Generator[None, None, None]:
    """Save a headed mp4 for each ODD test, including desktop-then-ODD sessions."""
    slug = slugify_nodeid(request.node.nodeid)
    recording = None
    page: Page | None = None
    if "run_odd_app" in request.fixturenames and is_headed_run(request.config):
        page = request.getfixturevalue("run_odd_app")
        recording = start_test_recording(
            context=page.context,
            page=page,
            slug=slug,
            record_screencast=True,
        )

    yield

    video_path = None
    if recording is not None and page is not None:
        artifacts = stop_test_recording(page.context, recording)
        video_path = artifacts.video_path
    if video_path is None:
        video_path = finalize_workflow_video(request.node.nodeid, slug)
    else:
        take_workflow_segments(request.node.nodeid)
    if video_path is not None:
        request.node.user_properties.append(("video_path", str(video_path)))
        log_path("Playwright video", video_path, kind="video")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Generator[None, Any, None]:
    """Embed the ODD workflow video in the HTML report."""
    outcome = yield
    report = outcome.get_result()
    if report.when != "teardown":
        return
    extras: list = []
    for name, path_str in item.user_properties:
        if name != "video_path":
            continue
        path = Path(path_str)
        if not path.exists():
            continue
        relative = path_relative_to_report(path)
        extras.append(html_extras.html(video_embed_html(relative, path)))
        extras.append(html_extras.url(relative, name="Download video"))
    if extras:
        report.extras = getattr(report, "extras", []) + extras

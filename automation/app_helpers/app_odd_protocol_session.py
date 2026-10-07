"""Sequential desktop-app and ODD sessions for App×ODD protocol workflows."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from contextlib import contextmanager

from playwright.sync_api import Page

import open_app
from automation.app_helpers.reporting import record_workflow_video


def _stop_process(process: subprocess.Popen | None) -> None:
    """Stop an app process started by this session."""
    if process is None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


@contextmanager
def desktop_app() -> Iterator[Page]:
    """Launch or attach to the desktop app, then cleanly release it."""
    process = None
    playwright = None
    browser = None
    try:
        if open_app.should_attach_only():
            playwright, browser, page = open_app.connect_playwright()
        else:
            process, playwright, browser, page = open_app.launch_and_connect()
        open_app.prepare_app_page(page)
        with record_workflow_video(page, "desktop"):
            yield page
    finally:
        if browser is not None:
            browser.close()
        if playwright is not None:
            playwright.stop()
        _stop_process(process)


@contextmanager
def odd_app(robot_ip: str) -> Iterator[Page]:
    """Attach to the Flex ODD after desktop provisioning is complete."""
    playwright = None
    browser = None
    try:
        playwright, browser, page = open_app.connect_odd_playwright(host=robot_ip)
        with record_workflow_video(page, "odd"):
            yield page
    finally:
        if browser is not None:
            browser.close()
        if playwright is not None:
            playwright.stop()

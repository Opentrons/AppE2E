"""Pytest configuration shared by Opentrons app and ODD E2E suites."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from _pytest.config import Config
from _pytest.nodes import Item
from _pytest.python import Function

from automation.app_helpers.reporting import ensure_test_results_dir, report_html_path
from automation.app_helpers.test_progress import SLOW_TEST_THRESHOLD_S, safe_print
from utility import _pause_for_debugging, troubleshoot_and_pause


def pytest_addoption(parser: pytest.Parser) -> None:
    """Shared CLI options for app and ODD suites.

    Registered here so the UI runner can always pass them. Options in
    ``tests/app/conftest.py`` are invisible unless that directory is collected.
    """
    parser.addoption(
        "--robot-ip",
        action="store",
        default=None,
        help="Robot IP for Wi-Fi / ODD CDP (overrides ROBOT_IP env var). Any address works.",
    )
    parser.addoption(
        "--robot-name",
        action="store",
        default=None,
        help="Robot display name on the Devices page (overrides ROBOT_NAME env var).",
    )
    parser.addoption(
        "--robot-profile",
        action="store",
        default=None,
        help=(
            "Launch profile (e.g. fake-robot starts make -C app dev + local robot-server). "
            "Overrides --robot-name when set."
        ),
    )


def _pause_on_failure_enabled(config: Config) -> bool:
    """Headed CLI pauses for Inspector; ``make test-ui`` sets E2E_NO_PAUSE=1 to continue."""
    import os

    from run_config import is_headed_run

    if os.environ.get("E2E_NO_PAUSE", "").strip().lower() in {"1", "true", "yes"}:
        return False
    return is_headed_run(config)


def pytest_collection_modifyitems(config: Config, items: list[Item]) -> None:
    """Wrap headed tests so failures open Playwright Inspector via page.pause()."""
    if _pause_on_failure_enabled(config):
        for item in items:
            if isinstance(item, Function):
                item.obj = troubleshoot_and_pause(item.obj)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: Item, call: pytest.CallInfo) -> Generator[None, Any, None]:
    """Pause on fixture setup failure; mark call bodies that exceed the slow threshold."""
    outcome = yield
    report = outcome.get_result()
    if report.failed and call.when == "setup" and _pause_on_failure_enabled(item.config):
        error = report.longrepr if isinstance(report.longrepr, BaseException) else None
        _pause_for_debugging(item.nodeid, error, item=item)
    if call.when == "call" and report.duration > SLOW_TEST_THRESHOLD_S:
        # Hard timeout is 500s; still flag anything that took longer than 300s.
        item.user_properties.append(("slow_over_300s", f"{report.duration:.1f}"))
        if item.get_closest_marker("slow") is None:
            item.add_marker(pytest.mark.slow)
        safe_print(
            f"  [slow] {item.nodeid} took {report.duration:.1f}s "
            f"(threshold {SLOW_TEST_THRESHOLD_S:.0f}s; hard timeout 500s)"
        )


def pytest_configure(config: Any) -> None:
    """Create today's test-results day folder and point the HTML report there."""
    from run_config import is_headed_run, publish_playwright_headless_mode

    publish_playwright_headless_mode(headless=not is_headed_run(config))
    day_dir = ensure_test_results_dir()
    config.option.htmlpath = str(report_html_path())
    output = getattr(config.option, "output", None)
    if output is None or str(output).startswith("test-results"):
        config.option.output = str(day_dir / "pw-artifacts")


def pytest_sessionstart(session: pytest.Session) -> None:
    """Ensure artifacts directory exists before tests begin."""
    ensure_test_results_dir()


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Guarantee artifacts directory exists before report generation."""
    ensure_test_results_dir()

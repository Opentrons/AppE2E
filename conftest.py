"""Pytest configuration shared by Opentrons app and ODD E2E suites."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from _pytest.config import Config
from _pytest.nodes import Item
from _pytest.python import Function

from automation.app_helpers.reporting import ensure_test_results_dir
from utility import _pause_for_debugging, troubleshoot_and_pause


def pytest_addoption(parser: pytest.Parser) -> None:
    """Shared CLI options for app and ODD suites."""
    parser.addoption(
        "--robot-ip",
        action="store",
        default=None,
        help="Robot IP for Wi-Fi / ODD CDP (overrides ROBOT_IP env var). Any address works.",
    )


def pytest_collection_modifyitems(config: Config, items: list[Item]) -> None:
    """Wrap headed tests so failures open Playwright Inspector via page.pause()."""
    from run_config import is_headed_run

    if is_headed_run(config):
        for item in items:
            if isinstance(item, Function):
                item.obj = troubleshoot_and_pause(item.obj)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: Item, call: pytest.CallInfo) -> Generator[None, Any, None]:
    """Same pause path as ``troubleshoot_and_pause`` when fixture setup fails."""
    from run_config import is_headed_run

    outcome = yield
    report = outcome.get_result()
    if report.failed and call.when == "setup" and is_headed_run(item.config):
        error = report.longrepr if isinstance(report.longrepr, BaseException) else None
        _pause_for_debugging(item.nodeid, error, item=item)


def pytest_configure(config: Any) -> None:
    """Create test-results directory if it doesn't exist."""
    ensure_test_results_dir()


def pytest_sessionstart(session: pytest.Session) -> None:
    """Ensure artifacts directory exists before tests begin."""
    ensure_test_results_dir()


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Guarantee artifacts directory exists before report generation."""
    ensure_test_results_dir()

"""Calibration suite: Flex setup gate, progress banners, and timing table."""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Generator
from typing import Any

import pytest

from automation.app_helpers.test_progress import (
    begin_test_timing,
    clear_test_timing_context,
    finish_test_timing,
    format_elapsed,
    make_suite_logstart,
    print_timing_table,
    reset_timing_report,
    safe_print,
)

pytest_runtest_logstart = make_suite_logstart("calibration")

_SKIP_PROMPT_ENV = "SKIP_FLEX_SETUP_PROMPT"


def _confirm_flex_setup(*, request: pytest.FixtureRequest) -> None:
    """Ask the operator to confirm physical Flex prep before destructive/calibration work."""
    if os.environ.get(_SKIP_PROMPT_ENV, "").strip().lower() in {"1", "true", "yes"}:
        safe_print(f"  -> Skipping Flex setup prompt ({_SKIP_PROMPT_ENV} set)")
        return

    prompt = (
        "\n"
        "Have you set up your Flex?\n"
        "  Recommended before device reset / calibration:\n"
        "  - Gripper calibrated (manual — not automated here)\n"
        "  - Deck configuration set for attached modules\n"
        "  - Modules attached, powered, and cool\n"
        "  - Calibration adapters + pipette probe ready\n"
        "\n"
        "Continue? [y/N]: "
    )

    capmanager = request.config.pluginmanager.get_plugin("capturemanager")
    if capmanager is not None:
        capmanager.suspend_global_capture(in_=True)
    try:
        if not sys.stdin.isatty():
            pytest.exit(
                "Flex setup confirmation needs an interactive terminal. "
                f"Re-run headed with a TTY, or set {_SKIP_PROMPT_ENV}=1 to skip.",
                returncode=1,
            )
        answer = input(prompt).strip().lower()
    finally:
        if capmanager is not None:
            capmanager.resume_global_capture()

    if answer not in {"y", "yes"}:
        pytest.exit("Aborted: Flex not confirmed set up.", returncode=1)

    safe_print("  [ok] Flex setup confirmed")


@pytest.fixture(scope="session", autouse=True)
def confirm_flex_setup(request: pytest.FixtureRequest) -> None:
    """CLI gate once per calibration session: have you set up your Flex?"""
    reset_timing_report()
    _confirm_flex_setup(request=request)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item: pytest.Item) -> Generator[None, Any, None]:
    """Collect per-test wall time and associate step timings with the test case."""
    begin_test_timing(item.name)
    started = time.perf_counter()
    outcome = yield
    wall_seconds = time.perf_counter() - started
    failed = outcome.excinfo is not None
    status = "failed" if failed else "passed"
    finish_test_timing(wall_seconds=wall_seconds, status=status)
    clear_test_timing_context()
    safe_print(f"  [time] {item.name} {status} in {format_elapsed(wall_seconds)}")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Print the calibration timing table at the end of the session."""
    del session, exitstatus
    print_timing_table(title="CALIBRATION TIMING SUMMARY")

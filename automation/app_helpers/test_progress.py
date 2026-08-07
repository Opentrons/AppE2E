"""Live progress lines for pytest runs (requires -s or capture disabled)."""

from __future__ import annotations

import sys


def log_banner(suite: str, test_name: str) -> None:
    """Print a visible banner when a test starts."""
    _safe_print(f"\n[{suite}] {test_name}")


def make_suite_logstart(suite: str):
    """Return a ``pytest_runtest_logstart`` hook that prints a suite banner."""

    def pytest_runtest_logstart(nodeid: str, location: tuple[str, int, str]) -> None:
        log_banner(suite, location[2])

    return pytest_runtest_logstart


def _safe_print(message: str) -> None:
    """Print to stdout without crashing on Windows cp1252 consoles."""
    try:
        print(message, flush=True)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        print(message.encode(encoding, errors="replace").decode(encoding), flush=True)


def log_step(message: str) -> None:
    """Print an in-progress step line."""
    _safe_print(f"  -> {message}")


def log_done(message: str = "done") -> None:
    """Print a completion line for the current step or test."""
    _safe_print(f"  [ok] {message}")

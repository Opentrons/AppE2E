"""Live progress lines and timing tables for pytest runs."""

from __future__ import annotations

import inspect
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_step_started_at: float | None = None
_timed_call_depth = 0
_current_test: str | None = None
_event_sink: Callable[[dict[str, object]], None] | None = None


def _caller_location(*, depth: int = 1) -> dict[str, object]:
    """Return the repo-relative file and 1-based line of the calling frame."""
    frame = inspect.currentframe()
    try:
        for _ in range(depth + 1):
            if frame is None:
                return {}
            frame = frame.f_back
        if frame is None:
            return {}
        path = Path(frame.f_code.co_filename).resolve()
        try:
            relative = path.relative_to(_REPO_ROOT).as_posix()
        except ValueError:
            relative = path.as_posix()
        return {"file": relative, "line": int(frame.f_lineno)}
    finally:
        del frame


@dataclass
class TimingStep:
    """One timed step within a test case."""

    label: str
    seconds: float
    depth: int = 1
    pending: bool = False


@dataclass
class TestTiming:
    """Collected timings for a single test function."""

    name: str
    steps: list[TimingStep] = field(default_factory=list)
    wall_seconds: float | None = None
    status: str = "passed"


_tests: list[TestTiming] = []
_tests_by_name: dict[str, TestTiming] = {}


def set_event_sink(sink: Callable[[dict[str, object]], None] | None) -> None:
    """Set an optional structured-event consumer used by the UI runner."""
    global _event_sink
    _event_sink = sink


def _emit(event: dict[str, object]) -> None:
    if _event_sink is not None:
        _event_sink(event)


def _current_record() -> TestTiming | None:
    if _current_test is None:
        return None
    record = _tests_by_name.get(_current_test)
    if record is None:
        record = TestTiming(name=_current_test)
        _tests_by_name[_current_test] = record
        _tests.append(record)
    return record


def begin_test_timing(test_name: str) -> None:
    """Start collecting timings for a test case (call from pytest hooks)."""
    global _current_test
    _current_test = test_name
    if test_name not in _tests_by_name:
        record = TestTiming(name=test_name)
        _tests_by_name[test_name] = record
        _tests.append(record)


def finish_test_timing(*, wall_seconds: float, status: str = "passed") -> None:
    """Attach wall-clock duration and status to the current test."""
    record = _current_record()
    if record is None:
        return
    record.wall_seconds = wall_seconds
    record.status = status


def clear_test_timing_context() -> None:
    """Clear the active test name after a test finishes."""
    global _current_test
    _current_test = None


def begin_timing_step(label: str, *, depth: int = 1) -> int | None:
    """Reserve a table row in start-order. Returns an index to finish later."""
    record = _current_record()
    if record is None:
        return None
    record.steps.append(TimingStep(label=label, seconds=0.0, depth=depth, pending=True))
    return len(record.steps) - 1


def finish_timing_step(index: int | None, seconds: float) -> None:
    """Fill in the duration for a previously started step."""
    if index is None:
        return
    record = _current_record()
    if record is None or index >= len(record.steps):
        return
    step = record.steps[index]
    step.seconds = seconds
    step.pending = False


def record_timing(label: str, seconds: float, *, depth: int = 1) -> None:
    """Record a completed step duration under the active test case."""
    record = _current_record()
    if record is None:
        return
    record.steps.append(TimingStep(label=label, seconds=seconds, depth=depth))


def reset_timing_report() -> None:
    """Clear collected timings (useful between sessions or in tests)."""
    global _current_test, _step_started_at, _timed_call_depth
    _tests.clear()
    _tests_by_name.clear()
    _current_test = None
    _step_started_at = None
    _timed_call_depth = 0


def log_banner(suite: str, test_name: str) -> None:
    """Print a visible banner when a test starts."""
    safe_print(f"\n[{suite}] {test_name}")


def make_suite_logstart(suite: str):
    """Return a ``pytest_runtest_logstart`` hook that prints a suite banner."""

    def pytest_runtest_logstart(nodeid: str, location: tuple[str, int, str]) -> None:
        log_banner(suite, location[2])

    return pytest_runtest_logstart


def safe_print(message: str) -> None:
    """Print to stdout without crashing on Windows cp1252 consoles."""
    try:
        print(message, flush=True)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        print(message.encode(encoding, errors="replace").decode(encoding), flush=True)


def format_elapsed(seconds: float) -> str:
    """Format a duration for progress lines and tables."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{int(minutes)}m {secs:04.1f}s"
    hours, minutes = divmod(int(minutes), 60)
    return f"{hours}h {minutes}m {secs:04.1f}s"


def log_step(message: str) -> None:
    """Print an in-progress step line and start the step timer."""
    global _step_started_at
    _step_started_at = time.perf_counter()
    safe_print(f"  -> {message}")
    _emit({"type": "step_start", "label": message, **_caller_location()})


def log_done(message: str = "done") -> None:
    """Print a completion line, including elapsed time since the last ``log_step``."""
    global _step_started_at
    seconds: float | None = None
    suffix = ""
    if _step_started_at is not None:
        seconds = time.perf_counter() - _step_started_at
        suffix = f" ({format_elapsed(seconds)})"
        record_timing(message, seconds, depth=max(_timed_call_depth, 1))
        _step_started_at = None
    safe_print(f"  [ok] {message}{suffix}")
    _emit({"type": "step_done", "label": message, "seconds": seconds, **_caller_location()})


def log_info(message: str, *, kind: str = "info", depth: int = 1) -> None:
    """Print a terminal-style finding (serial, path, note) and emit it to the UI runner."""
    safe_print(f"  · {message}")
    _emit({"type": "log", "kind": kind, "label": message, **_caller_location(depth=depth)})


def log_path(label: str, path: str | Path, *, kind: str = "path") -> None:
    """Print and emit a labeled filesystem path for the UI progress panel."""
    rendered = Path(path).as_posix() if isinstance(path, Path) else str(path)
    log_info(f"{label}: {rendered}", kind=kind, depth=2)


def run_timed(label: str, fn: Callable[..., T], *args: object, **kwargs: object) -> T:
    """Run ``fn``, logging start/finish with elapsed time (safe to nest)."""
    global _timed_call_depth
    location = _caller_location()
    safe_print(f"  -> {label}")
    _emit({"type": "step_start", "label": label, **location})
    started = time.perf_counter()
    _timed_call_depth += 1
    depth = _timed_call_depth
    step_index = begin_timing_step(label, depth=depth)
    try:
        return fn(*args, **kwargs)
    finally:
        seconds = time.perf_counter() - started
        finish_timing_step(step_index, seconds)
        safe_print(f"  [ok] {label} ({format_elapsed(seconds)})")
        _emit({"type": "step_done", "label": label, "seconds": seconds, **location})
        _timed_call_depth -= 1


def print_timing_table(*, title: str = "TIMING SUMMARY") -> None:
    """Print a table of step timings organized by test case."""
    if not _tests:
        return

    test_width = max(len("Test case"), max((len(t.name) for t in _tests), default=0), len("SUITE TOTAL"))
    step_width = len("Step")
    for test in _tests:
        for step in test.steps:
            indented = ("  " * (step.depth - 1)) + step.label
            step_width = max(step_width, len(indented), len("TOTAL (wall)"))
        if not test.steps:
            step_width = max(step_width, len("(no timed steps)"))
    dur_width = max(len("Duration"), max((len(format_elapsed(t.wall_seconds or 0.0)) for t in _tests), default=0), 10)
    for test in _tests:
        for step in test.steps:
            dur_width = max(dur_width, len(format_elapsed(step.seconds)))

    rule = f"{'─' * (test_width + step_width + dur_width + 6)}"
    header = f"{'Test case':<{test_width}}  {'Step':<{step_width}}  {'Duration':>{dur_width}}"

    safe_print("")
    safe_print(rule)
    safe_print(f" {title}")
    safe_print(rule)
    safe_print(header)
    safe_print(rule)

    suite_total = 0.0
    for test in _tests:
        status = test.status
        wall = test.wall_seconds
        if wall is not None:
            suite_total += wall

        if not test.steps:
            safe_print(
                f"{test.name:<{test_width}}  {'(no timed steps)':<{step_width}}  "
                f"{format_elapsed(wall or 0.0):>{dur_width}}"
            )
        else:
            first = True
            for step in test.steps:
                test_col = test.name if first else ""
                first = False
                label = ("  " * (step.depth - 1)) + step.label
                safe_print(
                    f"{test_col:<{test_width}}  {label:<{step_width}}  {format_elapsed(step.seconds):>{dur_width}}"
                )
            wall_label = f"TOTAL (wall, {status})"
            safe_print(f"{'':<{test_width}}  {wall_label:<{step_width}}  {format_elapsed(wall or 0.0):>{dur_width}}")
        safe_print(rule)

    safe_print(f"{'SUITE TOTAL':<{test_width}}  {'':<{step_width}}  {format_elapsed(suite_total):>{dur_width}}")
    safe_print(rule)
    safe_print("")

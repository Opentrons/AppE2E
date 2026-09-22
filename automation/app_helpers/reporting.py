"""Test result directories, tracing, and artifact paths for pytest-html reports.

Artifacts land under ``test-results/YYYY-MM/YYYY-MM-DD/`` so runs are grouped by
month and day. ``test-results/latest`` is a symlink to today's day folder.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from playwright.sync_api import BrowserContext, Page
from playwright.sync_api import Error as PlaywrightError

from automation.app_helpers.screencast_recorder import ScreencastRecorder

TEST_RESULTS_ROOT = Path("test-results")
_ARTIFACT_SUBDIRS = ("videos", "traces", "screenshots", "pw-artifacts")


def results_day_dir(day: date | None = None) -> Path:
    """Return ``test-results/YYYY-MM/YYYY-MM-DD`` for ``day`` (default: today)."""
    d = day or date.today()
    return TEST_RESULTS_ROOT / d.strftime("%Y-%m") / d.strftime("%Y-%m-%d")


def videos_dir(day: date | None = None) -> Path:
    """Videos subdirectory for the given day."""
    return results_day_dir(day) / "videos"


def traces_dir(day: date | None = None) -> Path:
    """Traces subdirectory for the given day."""
    return results_day_dir(day) / "traces"


def screenshots_dir(day: date | None = None) -> Path:
    """Screenshots subdirectory for the given day."""
    return results_day_dir(day) / "screenshots"


def report_html_path(day: date | None = None) -> Path:
    """pytest-html report path for the given day."""
    return results_day_dir(day) / "report.html"


def app_console_log_path(day: date | None = None) -> Path:
    """Electron console log path for the given day."""
    return results_day_dir(day) / "app-console.log"


def path_relative_to_report(artifact: Path, day: date | None = None) -> str:
    """Return a path to ``artifact`` relative to that day's ``report.html`` directory."""
    day_dir = results_day_dir(day).resolve()
    try:
        return artifact.resolve().relative_to(day_dir).as_posix()
    except ValueError:
        return artifact.as_posix()


def ensure_test_results_dir(day: date | None = None) -> Path:
    """Create today's (or ``day``'s) result tree and refresh ``test-results/latest``."""
    day_dir = results_day_dir(day)
    for name in _ARTIFACT_SUBDIRS:
        (day_dir / name).mkdir(parents=True, exist_ok=True)

    TEST_RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    latest = TEST_RESULTS_ROOT / "latest"
    target = day_dir.relative_to(TEST_RESULTS_ROOT)
    try:
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(target)
    except OSError:
        # Symlinks can fail on some filesystems; day dirs still work.
        pass
    return day_dir


# Back-compat aliases used by older call sites (resolve to *today* at import time
# is wrong across midnight — prefer videos_dir() / traces_dir() / screenshots_dir()).
TEST_RESULTS_DIR = TEST_RESULTS_ROOT


def slugify_nodeid(nodeid: str) -> str:
    """Convert a pytest node ID to a filesystem-friendly slug."""
    test_identifier = nodeid.split("::")[-1]
    candidate = re.sub(r"[^A-Za-z0-9_.-]+", "_", test_identifier)
    candidate = candidate.strip("_")
    if not candidate:
        return "test"
    return candidate[:200]


def unique_artifact_path(directory: Path, slug: str, suffix: str) -> Path:
    """Return ``directory/slug{suffix}``, appending ``_N`` when the path exists."""
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{slug}{suffix}"
    counter = 1
    while destination.exists():
        destination = directory / f"{slug}_{counter}{suffix}"
        counter += 1
    return destination


def day_from_mtime(path: Path) -> date:
    """Return the local calendar day of ``path``'s modification time."""
    return datetime.fromtimestamp(path.stat().st_mtime).date()


@dataclass
class TestArtifacts:
    """Paths produced for a single test run."""

    slug: str
    trace_path: Path | None = None
    video_path: Path | None = None
    screenshot_path: Path | None = None


@dataclass
class ActiveTestRecording:
    """In-flight per-test recording state."""

    slug: str
    trace_path: Path
    artifacts: TestArtifacts
    video_path: Path | None = None
    screencast: ScreencastRecorder | None = None
    tracing_started: bool = False


def start_test_recording(
    *,
    context: BrowserContext,
    page: Page,
    slug: str,
    record_screencast: bool,
    tracing_screenshots: bool | None = None,
) -> ActiveTestRecording:
    """Start Playwright tracing and optional CDP screencast for one test.

    Chromium allows only one ``Page.startScreencast`` stream. Tracing with
    ``screenshots=True`` starts its own screencast, which replaces any active
    ``ScreencastRecorder`` (suite or per-test). Default: disable tracing
    screenshots whenever we record screencast video; callers can also pass
    ``tracing_screenshots=False`` when a session-scoped suite video is running.
    """
    ensure_test_results_dir()
    trace_path = unique_artifact_path(traces_dir(), slug, ".zip")
    video_path = unique_artifact_path(videos_dir(), slug, ".webm") if record_screencast else None
    if tracing_screenshots is None:
        tracing_screenshots = not record_screencast

    recording = ActiveTestRecording(
        slug=slug,
        trace_path=trace_path,
        video_path=video_path,
        artifacts=TestArtifacts(slug=slug, trace_path=trace_path, video_path=video_path),
    )

    try:
        context.tracing.start(
            screenshots=tracing_screenshots,
            snapshots=True,
            sources=True,
        )
        recording.tracing_started = True
    except PlaywrightError as error:
        print(f"\n⚠️  Unable to start tracing for {slug}: {error}")

    if record_screencast and video_path is not None:
        screencast = ScreencastRecorder(page, video_path)
        try:
            screencast.start()
            recording.screencast = screencast
        except PlaywrightError as error:
            print(f"\n⚠️  Unable to start screencast for {slug}: {error}")
            recording.video_path = None
            recording.artifacts.video_path = None

    return recording


def stop_test_recording(
    context: BrowserContext,
    recording: ActiveTestRecording,
) -> TestArtifacts:
    """Stop tracing and screencast, returning saved artifact paths."""
    artifacts = recording.artifacts

    if recording.screencast is not None:
        saved_video = recording.screencast.stop()
        if saved_video is None:
            artifacts.video_path = None
        else:
            artifacts.video_path = saved_video

    if recording.tracing_started:
        try:
            context.tracing.stop(path=str(recording.trace_path))
            artifacts.trace_path = recording.trace_path
        except PlaywrightError as error:
            print(f"\n⚠️  Unable to save trace for {recording.slug}: {error}")
            artifacts.trace_path = None

    return artifacts


def capture_failure_screenshot(page: Page, slug: str) -> Path | None:
    """Save a full-page screenshot when a test fails."""
    ensure_test_results_dir()
    screenshot_path = unique_artifact_path(screenshots_dir(), slug, ".png")
    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
        return screenshot_path
    except PlaywrightError as error:
        print(f"\n⚠️  Unable to save failure screenshot for {slug}: {error}")
        return None

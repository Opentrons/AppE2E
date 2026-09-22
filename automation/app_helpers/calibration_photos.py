"""Beginning / middle / end screenshots for calibration suite tests (no video)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from automation.app_helpers.reporting import ensure_test_results_dir, screenshots_dir, unique_artifact_path
from automation.app_helpers.test_progress import log_path

CalibrationPhotoPhase = Literal["beginning", "middle", "end"]


@dataclass
class CalibrationPhotoSession:
    """Capture up to three milestone screenshots for one calibration test."""

    page: Page
    slug: str
    paths: dict[CalibrationPhotoPhase, Path] = field(default_factory=dict)

    def capture(self, phase: CalibrationPhotoPhase) -> Path | None:
        """Save a full-page screenshot for ``phase`` (first call wins per phase)."""
        if phase in self.paths:
            return self.paths[phase]
        ensure_test_results_dir()
        path = unique_artifact_path(screenshots_dir(), f"{self.slug}_{phase}", ".png")
        try:
            self.page.screenshot(path=str(path), full_page=True)
        except PlaywrightError as error:
            print(f"\n⚠️  Unable to save {phase} screenshot for {self.slug}: {error}")
            return None
        self.paths[phase] = path
        log_path(f"Calibration photo ({phase})", path, kind="screenshot")
        return path


_active: CalibrationPhotoSession | None = None


def bind_calibration_photos(page: Page, slug: str) -> CalibrationPhotoSession:
    """Start a photo session for the current test (used by calibration conftest)."""
    global _active
    session = CalibrationPhotoSession(page=page, slug=slug)
    _active = session
    return session


def unbind_calibration_photos() -> None:
    """Clear the active photo session after the test finishes."""
    global _active
    _active = None


def capture_calibration_photo(phase: CalibrationPhotoPhase) -> Path | None:
    """Capture a milestone photo when a calibration photo session is active."""
    if _active is None:
        return None
    return _active.capture(phase)

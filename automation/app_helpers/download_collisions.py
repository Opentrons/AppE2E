"""Avoid OS \"file already exists\" replace dialogs during File Manager downloads.

Electron ``file-saver`` / Chromium downloads write to the user's Downloads folder
under stable names. A second download of the same name pops a native Replace
sheet that Playwright/Stagewright cannot see or dismiss reliably.

General approach: remove (or relocate) the expected target paths *before*
clicking Download / Delete. Prefer prevention over clicking Replace.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_DOWNLOADS_DIR = Path.home() / "Downloads"


def file_manager_download_names(robot_name: str) -> tuple[str, ...]:
    """Stable filenames File Manager writes for ``robot_name``."""
    return (
        f"{robot_name}_logs.zip",
        f"{robot_name}-calibration.json",
        f"{robot_name}-run-records.zip",
    )


def clear_download_collisions(
    *filenames: str,
    downloads_dir: Path | None = None,
) -> list[Path]:
    """Delete existing download targets so the next save won't prompt Replace.

    Returns the paths that were removed. Missing files are ignored.
    """
    root = downloads_dir if downloads_dir is not None else DEFAULT_DOWNLOADS_DIR
    removed: list[Path] = []
    for name in filenames:
        path = root / name
        if path.is_file():
            path.unlink()
            removed.append(path)
    return removed


def clear_file_manager_downloads(
    robot_name: str,
    *,
    downloads_dir: Path | None = None,
) -> list[Path]:
    """Clear all known File Manager download names for ``robot_name``."""
    return clear_download_collisions(
        *file_manager_download_names(robot_name),
        downloads_dir=downloads_dir,
    )

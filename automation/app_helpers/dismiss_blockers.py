"""Pytest-level click retry: snapshot blockers, dismiss toasts, retry once."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from automation.app_helpers.app_readiness import dismiss_pointer_blockers
from automation.app_helpers.reporting import (
    ensure_test_results_dir,
    screenshots_dir,
    slugify_nodeid,
    unique_artifact_path,
)
from automation.app_helpers.test_progress import safe_print

_RETRY_GUARD = threading.local()


def capture_blocker_snapshot(page: Page, nodeid: str) -> Path | None:
    """Screenshot the UI that blocked a click, before any dismiss attempt."""
    ensure_test_results_dir()
    slug = f"{slugify_nodeid(nodeid)}_blocker"
    screenshot_path = unique_artifact_path(screenshots_dir(), slug, ".png")
    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
    except Exception as error:
        safe_print(f"  [dismiss_blockers] snapshot failed: {error}")
        return None
    safe_print(f"  [dismiss_blockers] snapshot {screenshot_path}")
    return screenshot_path


def _in_retry() -> bool:
    return bool(getattr(_RETRY_GUARD, "active", False))


@contextmanager
def _retry_guard() -> Iterator[None]:
    """Prevent nested Locator.click wraps while dismissing / retrying."""
    _RETRY_GUARD.active = True
    try:
        yield
    finally:
        _RETRY_GUARD.active = False


@contextmanager
def install_click_dismiss_fallback(page: Page, *, nodeid: str) -> Iterator[list[Path]]:
    """Wrap ``Locator.click`` for this test: on timeout, snapshot → dismiss toast → retry.

    Mid-flow dismiss only clears toasts (not slideouts / confirm modals). Nested
    clicks used while dismissing use the original Playwright click.
    """
    snapshots: list[Path] = []
    original_click = Locator.click

    def wrapped_click(locator: Locator, *args: object, **kwargs: object) -> None:
        if _in_retry():
            return original_click(locator, *args, **kwargs)
        try:
            return original_click(locator, *args, **kwargs)
        except PlaywrightTimeoutError as error:
            with _retry_guard():
                # Prefer the locator's page; fall back to the fixture page.
                target = locator.page if hasattr(locator, "page") else page
                snapshot = capture_blocker_snapshot(target, nodeid)
                if snapshot is not None:
                    snapshots.append(snapshot)
                if not dismiss_pointer_blockers(target):
                    raise error
                safe_print("  [dismiss_blockers] dismissed toast; retrying click")
                return original_click(locator, *args, **kwargs)

    Locator.click = wrapped_click  # type: ignore[method-assign]
    try:
        yield snapshots
    finally:
        Locator.click = original_click  # type: ignore[method-assign]

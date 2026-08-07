"""Shared headed-debug helpers for app and ODD E2E tests."""

from __future__ import annotations

import functools

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


def _page_from_value(value: object) -> Page | None:
    """Return a Playwright Page from a test arg or a page object that exposes ``.page``."""
    if isinstance(value, Page):
        return value
    page = getattr(value, "page", None)
    if isinstance(page, Page):
        return page
    return None


def _find_page(*args: object, item: object | None = None, **kwargs: object) -> Page | None:
    """Find a Playwright Page from test/fixture args or a pytest item."""
    for arg in args:
        if (found := _page_from_value(arg)) is not None:
            return found
    for val in kwargs.values():
        if (found := _page_from_value(val)) is not None:
            return found

    if item is not None:
        funcargs = getattr(item, "funcargs", None)
        if isinstance(funcargs, dict):
            for key in ("run_local_app", "run_odd_app", "page"):
                val = funcargs.get(key)
                if isinstance(val, Page):
                    return val
            for val in funcargs.values():
                if (found := _page_from_value(val)) is not None:
                    return found
        session = getattr(item, "session", None)
        stashed = getattr(session, "playwright_debug_page", None)
        if isinstance(stashed, Page):
            return stashed

    return None


def _pause_for_debugging(
    where: str,
    error: BaseException | None,
    *args: object,
    item: object | None = None,
    **kwargs: object,
) -> None:
    """Print failure context and open Playwright Inspector (shared by decorator + setup hook)."""
    if error is not None:
        print(f"\n🛑 '{where}' failed due to: {type(error).__name__} - {error}")
    else:
        print(f"\n🛑 '{where}' failed")
    print("Pausing execution for debugging...")

    page = _find_page(*args, item=item, **kwargs)
    if page is not None:
        page.pause()
        return

    print("⚠️  Could not find a Playwright page to pause.")
    print("    You can still debug the console state.")


def troubleshoot_and_pause(func):  # type: ignore[no-untyped-def]
    """Wrap a test so failures call ``page.pause()`` in headed runs.

    Pytest fixture setup is not wrapped automatically — root ``conftest.py`` calls
    ``_pause_for_debugging`` from ``pytest_runtest_makereport`` on setup failures.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def]
        try:
            return func(*args, **kwargs)
        except (AssertionError, PlaywrightTimeoutError, PlaywrightError, Exception) as e:
            _pause_for_debugging(func.__name__, e, *args, **kwargs)
            raise

    return wrapper

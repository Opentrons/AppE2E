"""Drive a Flex ODD the same way the ABR runners do.

``connect`` attaches to the touchscreen Chromium on port 9223 (Developer Tools
must be on) and opens the protocols list. ``tap`` clicks the center of a
control. ``wait_for_run_outcome`` blocks until the run summary appears.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager

from playwright.sync_api import Locator, Page, sync_playwright

from automation.app_helpers.screencast_recorder import CDP_HTTP_ATTR
from open_app import ODD_CDP_PORT

_SETTLE_MS = 1_500
_DEFAULT_TIMEOUT_MS = 300_000


@contextmanager
def connect(robot_ip: str) -> Iterator[Page]:
    """Attach to the Flex ODD over CDP and open the protocols list."""
    with sync_playwright() as playwright:
        cdp_url = f"http://{robot_ip}:{ODD_CDP_PORT}"
        browser = playwright.chromium.connect_over_cdp(cdp_url)
        setattr(browser, CDP_HTTP_ATTR, cdp_url)
        page = browser.contexts[0].pages[0]
        goto_route(page, "#/protocols")
        try:
            yield page
        finally:
            browser.close()


def goto_route(page: Page, route: str) -> None:
    """Set the ODD hash route and wait for the screen to settle."""
    page.evaluate("route => window.location.hash = route", route)
    page.wait_for_timeout(_SETTLE_MS)


def tap(
    page: Page,
    target: str | Locator,
    exact: bool = True,
    timeout: float = _DEFAULT_TIMEOUT_MS,
) -> None:
    """Tap the center of visible text or a locator."""
    if isinstance(target, str):
        target = page.get_by_text(target, exact=exact).first
    target.wait_for(state="visible", timeout=timeout)
    target.scroll_into_view_if_needed(timeout=timeout)
    box = target.bounding_box(timeout=timeout)
    if box is None:
        raise RuntimeError("ODD tap target has no bounding box")
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.wait_for_timeout(_SETTLE_MS)


def protocol_row(
    page: Page,
    name: str,
    date_added: str,
    timeout: float = _DEFAULT_TIMEOUT_MS,
) -> Locator:
    """Return the protocols-list row whose name and Date Added both match."""
    cells = page.get_by_text(name, exact=True)
    cells.first.wait_for(state="visible", timeout=timeout)
    for i in range(cells.count()):
        row = cells.nth(i).locator("xpath=ancestor::div[2]")
        if date_added in (row.inner_text() or ""):
            return row
    raise LookupError(f"no {name!r} row with Date Added {date_added!r}")


def errored(page: Page) -> bool:
    """Return whether the ODD is showing Launch recovery mode."""
    return page.get_by_text("Launch recovery mode", exact=True).is_visible()


def wait_for_run_outcome(page: Page, timeout: float = 0) -> str:
    """Block until the run finishes or errors.

    ``timeout`` is milliseconds. ``0`` waits indefinitely. The summary header is
    one of "Run completed", "Run completed with warnings", "Run failed",
    "Run canceled", or "Run canceled with errors". Returns ``"completed"`` or
    ``"error"``.
    """
    summary = page.get_by_text(re.compile(r"^Run (completed|failed|canceled)")).first
    recovery = page.get_by_text("Launch recovery mode", exact=True)
    summary.or_(recovery).first.wait_for(state="visible", timeout=timeout)
    if errored(page):
        return "error"
    header = (summary.inner_text() or "").strip()
    page.mouse.click(40, 41)
    page.get_by_text("Return to dashboard", exact=True).wait_for(state="visible", timeout=_DEFAULT_TIMEOUT_MS)
    return "completed" if header.startswith("Run completed") else "error"


def reset(page: Page) -> None:
    """Return to the dashboard, then back to the protocols list."""
    tap(page, "Return to dashboard")
    # The tap only kicks off an async dismiss of the current run; the app calls
    # navigate('/dashboard') when that settles, which clobbers any route we set
    # in the meantime. Let it land before hash-routing away.
    page.wait_for_function("() => window.location.hash.startsWith('#/dashboard')", timeout=_DEFAULT_TIMEOUT_MS)
    goto_route(page, "#/protocols")
    # The list renders an empty state until useAllProtocolsQuery resolves.
    page.get_by_text("Date Added", exact=True).wait_for(state="visible", timeout=_DEFAULT_TIMEOUT_MS)

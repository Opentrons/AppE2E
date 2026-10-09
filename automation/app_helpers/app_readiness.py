"""Dismiss modals and slideouts that block navbar interaction."""

from __future__ import annotations

import re
import time

from playwright.sync_api import Locator, Page, expect

OVERLAY_SELECTOR = '[data-sentry-component="Overlay"]'
# Current Slideout close control (app/src/atoms/Slideout). Legacy testid kept as fallback.
SLIDEOUT_CLOSE_SELECTOR = 'button[aria-label="exit"], [data-testid^="Slideout_icon_close_"]'
TOAST_SELECTOR = '[data-testid^="Toast_"]'
MODAL_CLOSE_SELECTOR = '[data-testid^="ModalHeader_icon_close_"]'
LANGUAGE_MODAL_BUTTONS = ("Continue", "Use system language", "Don't change")
APP_SETTINGS_URL = re.compile(r"#/app-settings")
# Navbar gear menu debounces navigation by 300ms (see app/src/App/Navbar/index.tsx).
GEAR_NAV_DEBOUNCE_MS = 350


def dismiss_blocking_ui(page: Page, *, timeout: float = 15_000) -> None:
    """Close startup modals and slideouts so the app is ready for navigation."""
    _dismiss_language_modals(page)
    dismiss_blocking_toasts(page)
    close_visible_modals(page)
    close_visible_slideouts(page)
    click_visible_overlays(page)
    wait_for_overlays_hidden(page, timeout=timeout)


def dismiss_pointer_blockers(page: Page) -> bool:
    """Dismiss toasts that steal clicks without closing intentional slideouts/modals.

    Used by the ``dismiss_blockers`` pytest mark on click timeout. Full nav
    cleanup stays in ``dismiss_blocking_ui`` / ``click_when_ui_ready``.
    """
    return dismiss_blocking_toasts(page)


def click_when_ui_ready(page: Page, locator: Locator, *, timeout: float = 15_000) -> None:
    """Dismiss blocking UI, then click the target."""
    dismiss_blocking_ui(page, timeout=timeout)
    if APP_SETTINGS_URL.search(page.url):
        # Drain a pending gear-menu debounced navigate before leaving App Settings.
        page.wait_for_timeout(GEAR_NAV_DEBOUNCE_MS)
    locator.click()


def close_visible_slideouts(page: Page, *, deadline_s: float = 5.0, pause_ms: int = 400) -> bool:
    """Close on-screen slideouts. Returns True if any close was attempted.

    Collapsed slideouts stay mounted (for example the protocol import panel) and
    keep an ``exit`` button translated off the right edge. Playwright still
    reports that button as visible, so a visibility check alone spends the whole
    deadline clicking a control that is not on screen.
    """
    deadline = time.time() + deadline_s
    close_buttons = page.locator(SLIDEOUT_CLOSE_SELECTOR)
    closed_any = False

    while time.time() < deadline:
        on_screen = [index for index in range(close_buttons.count()) if _is_on_screen(page, close_buttons.nth(index))]
        if not on_screen:
            return closed_any
        close = close_buttons.nth(on_screen[0])
        closed_any = True
        # Slideout close buttons are fixed-position; Playwright may treat them as
        # outside the viewport even when visible.
        try:
            close.click(force=True, timeout=2_000)
        except Exception:
            page.keyboard.press("Escape")
        page.wait_for_timeout(pause_ms)
    return closed_any


def click_visible_overlays(page: Page, *, timeout_ms: float = 1_000) -> bool:
    """Click visible Overlay components to dismiss menus/slideouts. Returns True if any clicked."""
    overlays = page.locator(OVERLAY_SELECTOR)
    clicked_any = False
    for index in range(overlays.count()):
        overlay = overlays.nth(index)
        if not overlay.is_visible():
            continue
        clicked_any = True
        try:
            overlay.click(force=True, position={"x": 8, "y": 8}, timeout=timeout_ms)
        except Exception:
            pass
    return clicked_any


def dismiss_blocking_toasts(page: Page) -> bool:
    """Close visible toasts that intercept pointer events. Returns True if any closed."""
    toasts = page.locator(TOAST_SELECTOR)
    dismissed_any = False
    for index in range(toasts.count()):
        toast = toasts.nth(index)
        if not toast.is_visible():
            continue
        close = toast.get_by_role("button").first
        if close.count() == 0 or not close.is_visible():
            continue
        try:
            close.click(timeout=2_000)
            dismissed_any = True
        except Exception:
            continue
    return dismissed_any


def close_visible_modals(page: Page, *, timeout_ms: float = 2_000) -> bool:
    """Click ModalHeader close icons when present. Returns True if any close was attempted."""
    close_buttons = page.locator(MODAL_CLOSE_SELECTOR)
    closed_any = False
    for index in range(close_buttons.count()):
        close = close_buttons.nth(index)
        if not close.is_visible():
            continue
        closed_any = True
        try:
            close.click(timeout=timeout_ms)
        except Exception:
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
    return closed_any


def wait_for_overlays_hidden(page: Page, *, timeout: float) -> None:
    """Wait until blocking overlay elements are no longer visible."""
    overlays = page.locator(OVERLAY_SELECTOR)
    visible_indexes = [index for index in range(overlays.count()) if overlays.nth(index).is_visible()]
    if not visible_indexes:
        return

    per_overlay_timeout = max(timeout / len(visible_indexes), 1_000)
    for index in visible_indexes:
        expect(overlays.nth(index)).to_be_hidden(timeout=per_overlay_timeout)


def _dismiss_language_modals(page: Page) -> None:
    """Click through optional language-selection modals on first launch."""
    for button_name in LANGUAGE_MODAL_BUTTONS:
        button = page.get_by_role("button", name=button_name)
        for index in range(button.count()):
            target = button.nth(index)
            # Hidden matches (a wizard "Continue" left in the DOM) must not burn
            # the click timeout once the app is already past this modal.
            if not target.is_visible():
                continue
            try:
                target.click(timeout=2_000)
            except Exception:
                continue
            break


def _is_on_screen(page: Page, locator: Locator) -> bool:
    """Return True when ``locator`` is visible and its center is in the viewport."""
    if not locator.is_visible():
        return False
    box = locator.bounding_box()
    if box is None or box["width"] <= 0 or box["height"] <= 0:
        return False
    viewport = _viewport_size(page)
    if viewport is None:
        return True
    width, height = viewport
    center_x = box["x"] + box["width"] / 2
    center_y = box["y"] + box["height"] / 2
    return 0 <= center_x < width and 0 <= center_y < height


def _viewport_size(page: Page) -> tuple[float, float] | None:
    """Return the layout viewport, including CDP targets with no Playwright viewport."""
    viewport = page.viewport_size
    if viewport is not None:
        width = float(viewport["width"])
        height = float(viewport["height"])
        if width > 0 and height > 0:
            return width, height
    try:
        size = page.evaluate("() => ({ width: window.innerWidth, height: window.innerHeight })")
    except Exception:
        return None
    width = float(size.get("width") or 0)
    height = float(size.get("height") or 0)
    if width <= 0 or height <= 0:
        return None
    return width, height

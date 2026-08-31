"""Shared base for Opentrons desktop app page objects."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from automation.base_page import BasePage


class AppBasePage(BasePage):
    """Base page with app-specific toast and slideout helpers."""

    def __init__(self, page: Page) -> None:
        """Bind the Playwright page via BasePage."""
        super().__init__(page)

    def dismiss_warning_toast(self) -> None:
        """Dismiss a warning toast if present (it can block clicks)."""
        toast = self.page.get_by_test_id("Toast_warning")
        if toast.count() == 0:
            return
        close = toast.locator("button").first
        if not close.is_visible():
            return
        close.click()
        expect(toast).to_be_hidden(timeout=5_000)

    def close_slideout_by_title(self, title: str) -> None:
        """Dismiss a slideout (app 4.x has no Slideout_title_* test ids)."""
        legacy_title = self.page.get_by_test_id(f"Slideout_title_{title}")
        done = self.page.get_by_text("Done", exact=True)
        if done.count() > 0 and done.is_visible():
            done.click()
        else:
            # Current Slideout close is aria-label="exit"; legacy testid kept as fallback.
            close = self.page.get_by_role("button", name="exit").or_(
                self.page.get_by_test_id(f"Slideout_icon_close_{title}")
            )
            if close.count() > 0 and close.first.is_visible():
                try:
                    close.first.click(force=True, timeout=2_000)
                except Exception:
                    self.page.keyboard.press("Escape")
            else:
                self.page.keyboard.press("Escape")
        if legacy_title.count() > 0:
            expect(legacy_title).to_have_count(0)
        else:
            # Closed slideouts unmount (see RobotSettingsAdvanced show* guards).
            expect(self.page.get_by_role("button", name="exit")).to_have_count(0)

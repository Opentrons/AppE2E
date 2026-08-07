"""ODD Robot Dashboard (home) page object."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

from automation.app_pages.base_app.app_base_page import AppBasePage


class OddHomePage(AppBasePage):
    """Flex ODD dashboard / home after CDP attach."""

    DASHBOARD_URL = re.compile(r"#?/dashboard")
    PROTOCOLS_URL = re.compile(r"#?/protocols/?$")

    def __init__(self, page: Page) -> None:
        """Bind the Playwright page for the remote ODD window."""
        super().__init__(page)

    @property
    def dashboard_link(self) -> Locator:
        """Top-nav link to the robot dashboard (robot name)."""
        return self.page.locator('a[href*="/dashboard"]').first

    @property
    def protocols_nav(self) -> Locator:
        """Top-nav Protocols link."""
        return self.page.get_by_role("link", name="Protocols")

    def expect_alive(self, *, timeout: float = 15_000) -> None:
        """Assert the attached page is the Opentrons ODD UI (title + renderer URL)."""
        expect(self.page).to_have_title(re.compile(r"opentrons", re.IGNORECASE), timeout=timeout)
        expect(self.page).to_have_url(re.compile(r"index\.html", re.IGNORECASE), timeout=timeout)

    def dismiss_welcome_modal_if_present(self) -> None:
        """Dismiss the post-unboxing Welcome modal when it appears."""
        next_btn = self.page.get_by_role("button", name="Next")
        if next_btn.count() > 0 and next_btn.first.is_visible():
            next_btn.first.click()
            expect(next_btn).to_have_count(0, timeout=10_000)

    def open_dashboard(self) -> None:
        """Open the Robot Dashboard from the top nav."""
        self.dismiss_welcome_modal_if_present()
        expect(self.dashboard_link).to_be_visible(timeout=15_000)
        self.dashboard_link.click()
        expect(self.page).to_have_url(self.DASHBOARD_URL, timeout=15_000)
        self.dismiss_welcome_modal_if_present()

    def expect_dashboard_content(self) -> None:
        """Assert dashboard shows recent-run carousel or the empty state."""
        run_again = self.page.get_by_text("Run again", exact=True)
        empty = self.page.get_by_text("No recent runs", exact=True)
        expect(run_again.or_(empty).first).to_be_visible(timeout=15_000)

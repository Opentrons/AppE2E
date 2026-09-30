"""Flex ODD robot dashboard."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from automation.app_pages.odd.odd_shell import OddShell


class OddHomePage(OddShell):
    """Flex ODD dashboard / home after CDP attach."""

    def __init__(self, page: Page) -> None:
        """Bind the Playwright page for the remote ODD window."""
        super().__init__(page)

    def expect_dashboard_content(self) -> None:
        """Assert dashboard shows recent-run carousel or the empty state."""
        run_again = self.page.get_by_text("Run again", exact=True)
        empty = self.page.get_by_text("No recent runs", exact=True)
        expect(run_again.or_(empty).first).to_be_visible(timeout=15_000)

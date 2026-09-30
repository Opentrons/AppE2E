"""Flex ODD Robot Settings list."""

from __future__ import annotations

from playwright.sync_api import Locator, Page, expect

from automation.app_pages.odd.odd_shell import OddShell


class OddSettingsPage(OddShell):
    """Robot Settings list and the drill-in screens that replace it in place.

    Toggle rows (LED lights, dev tools, and similar) stay on the list.
    Use ``open_setting`` for rows that push a child screen with a back button,
    such as Network settings or Touchscreen sleep.
    """

    def __init__(self, page: Page) -> None:
        """Bind the Playwright page for the remote ODD window."""
        super().__init__(page)

    def open(self) -> None:
        """Open Robot Settings from the top nav."""
        self.open_settings()

    def setting_button(self, name: str) -> Locator:
        """A settings row. The accessible name also includes the subtitle."""
        return self.page.get_by_role("button", name=name)

    def expect_settings_list(self) -> None:
        """Assert the settings list is showing."""
        expect(self.setting_button("Network settings")).to_be_visible(timeout=15_000)
        expect(self.setting_button("Robot system version")).to_be_visible()

    def open_setting(self, name: str) -> None:
        """Open a settings row that navigates to a child screen."""
        button = self.setting_button(name)
        expect(button).to_be_visible(timeout=15_000)
        button.scroll_into_view_if_needed()
        button.click()
        expect(self.page.get_by_role("button", name="Back to previous page")).to_be_visible(timeout=15_000)

    def back(self) -> None:
        """Return from a settings child screen to the settings list."""
        self.page.get_by_role("button", name="Back to previous page").click()
        expect(self.setting_button("Network settings")).to_be_visible(timeout=15_000)

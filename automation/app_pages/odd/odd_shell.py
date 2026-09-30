"""Shared Flex ODD top navigation.

Every ODD screen inherits this so a test can move between dashboard,
Protocols, Instruments, Settings, and the kebab menu with one call.
"""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

from automation.app_pages.base_app.app_base_page import AppBasePage


class OddShell(AppBasePage):
    """Top nav and route waits for the Flex On-Device Display."""

    DASHBOARD_URL = re.compile(r"#?/dashboard")
    PROTOCOLS_URL = re.compile(r"#?/protocols/?$")
    INSTRUMENTS_URL = re.compile(r"#?/instruments/?$")
    SETTINGS_URL = re.compile(r"#?/robot-settings/?$")
    DECK_CONFIGURATION_URL = re.compile(r"#?/deck-configuration")

    def __init__(self, page: Page) -> None:
        """Bind the Playwright page for the remote ODD window."""
        super().__init__(page)

    @property
    def dashboard_link(self) -> Locator:
        """Top-nav link to the robot dashboard (the robot name, which is truncated)."""
        return self.page.locator('a[href*="/dashboard"]').first

    @property
    def protocols_nav(self) -> Locator:
        """Top-nav Protocols link."""
        return self.page.get_by_role("link", name="Protocols")

    @property
    def instruments_nav(self) -> Locator:
        """Top-nav Instruments link."""
        return self.page.get_by_role("link", name="Instruments")

    @property
    def settings_nav(self) -> Locator:
        """Top-nav Settings link."""
        return self.page.get_by_role("link", name="Settings")

    @property
    def kebab_nav(self) -> Locator:
        """Top-nav overflow (kebab) menu button."""
        return self.page.get_by_role("button", name="overflow menu button")

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

    def _follow(self, link: Locator, url: re.Pattern[str], *, timeout: float = 15_000) -> None:
        """Click a top-nav link and wait until the hash route matches."""
        self.dismiss_welcome_modal_if_present()
        expect(link).to_be_visible(timeout=timeout)
        link.click()
        expect(self.page).to_have_url(url, timeout=timeout)
        self.dismiss_welcome_modal_if_present()

    def open_dashboard(self) -> None:
        """Open the Robot Dashboard from the top nav."""
        self._follow(self.dashboard_link, self.DASHBOARD_URL)

    def open_protocols(self) -> None:
        """Open the Protocols dashboard from the top nav."""
        self._follow(self.protocols_nav, self.PROTOCOLS_URL)

    def open_instruments(self) -> None:
        """Open the Instruments dashboard from the top nav."""
        self._follow(self.instruments_nav, self.INSTRUMENTS_URL)

    def open_settings(self) -> None:
        """Open Robot Settings from the top nav."""
        self._follow(self.settings_nav, self.SETTINGS_URL)

    def open_kebab(self) -> None:
        """Open the overflow menu and wait until Home gantry is visible."""
        self.dismiss_welcome_modal_if_present()
        expect(self.kebab_nav).to_be_visible(timeout=15_000)
        self.kebab_nav.click()
        expect(self.page.get_by_role("button", name="Home gantry")).to_be_visible(timeout=10_000)

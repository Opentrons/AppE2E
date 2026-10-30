"""Shared Flex ODD top navigation.

Every ODD screen inherits this so a test can move between dashboard,
Protocols, Instruments, Settings, and the kebab menu with one call.
Child screens use ``back_button`` for the ChildNavigation chevron.
"""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

from automation.app_helpers.locator_helpers import exact_text
from automation.app_pages.base_app.app_base_page import AppBasePage
from automation.app_pages.odd.odd_readings import OddReadings, readings_for


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
    def readings(self) -> OddReadings:
        """Values already read from this ODD, shared by every screen object."""
        return readings_for(self.page)

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

    @property
    def back_button(self) -> Locator:
        """ChildNavigation back button.

        ``aria-label`` is "Back to previous page" and stays English when the
        UI language changes. The chevron path is ``aria-roledescription="back"``.
        """
        return self.page.get_by_test_id("ChildNavigation_Back_Button")

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

    def dismiss_canceled_run_if_present(self, *, wait_ms: float = 0) -> None:
        """Leave the touchscreen when a test starts on the Run canceled splash.

        Canceling a protocol leaves the ODD on a full-screen button whose
        heading is "Run canceled". Tap that splash, then Return to dashboard.
        If tips are still on a pipette, remove them before the dashboard opens.
        ``wait_ms`` waits for the splash to appear. ``0`` only acts when it is
        already on screen.
        """
        from automation.app_helpers.test_progress import log_done, log_step

        splash = self.page.get_by_role("heading", name=exact_text("Run canceled"), level=1)
        returning = self._return_to_dashboard_button()
        if self._is_visible(self.protocols_nav) and not self._is_visible(splash):
            return
        if wait_ms > 0 and not self._is_visible(splash) and not self._is_visible(returning):
            try:
                expect(splash.or_(returning).first).to_be_visible(timeout=wait_ms)
            except AssertionError:
                return
        if not self._is_visible(splash) and not self._is_visible(returning):
            return

        if self._is_visible(splash):
            log_step("Run canceled splash is up after the protocol was canceled")
            splash_button = self.page.get_by_role("button").filter(has=splash)
            self.press(splash_button.first)
            expect(returning).to_be_visible(timeout=60_000)

        log_step("Return to dashboard after the canceled run")
        self.press(returning)
        self._finish_canceled_run()
        log_done("Dashboard is open after the canceled run")

    def _return_to_dashboard_button(self) -> Locator:
        """The summary LargeButton, not the full-screen button wrapped around it.

        The run summary is one outer ``<button>``. Its accessible name includes
        "Return to dashboard", and clicking that outer button does nothing once
        the splash is gone. The control that leaves the run is the inner button
        whose label is the paragraph "Return to dashboard".
        """
        label = self.page.locator("p", has_text=exact_text("Return to dashboard"))
        return label.locator("xpath=ancestor::button[1]")

    def _finish_canceled_run(self) -> None:
        """Wait out Return to dashboard, dropping leftover tips when the modal appears."""
        from automation.app_helpers.test_progress import log_step

        tips = self.page.get_by_text(exact_text("Remove any attached tips"))
        expect(tips.or_(self.dashboard_link).first).to_be_visible(timeout=60_000)
        if not self._is_visible(tips):
            expect(self.page).to_have_url(self.DASHBOARD_URL, timeout=60_000)
            return
        log_step("Tips are still attached after the canceled run")
        self.press(self.page.get_by_role("button", name=re.compile(r"^Begin removal$", re.IGNORECASE)))
        from automation.app_pages.odd.odd_drop_tip_wizard import OddDropTipWizard

        OddDropTipWizard(self.page).drop_in_waste_chute_without_blowout()
        expect(self.page).to_have_url(self.DASHBOARD_URL, timeout=60_000)

    def _is_visible(self, locator: Locator) -> bool:
        """True when the locator matches a visible element."""
        return locator.count() > 0 and locator.first.is_visible()

    def press(self, target: Locator) -> None:
        """Activate a control with a DOM click.

        A CDP pointer click on this touchscreen does not reach the React
        handler. ``dispatch_event('click')`` does.
        """
        expect(target).to_be_visible(timeout=15_000)
        target.scroll_into_view_if_needed()
        target.dispatch_event("click")

    def _follow(self, link: Locator, url: re.Pattern[str], *, timeout: float = 15_000) -> None:
        """Click a top-nav link and wait until the hash route matches."""
        self.dismiss_canceled_run_if_present()
        self.dismiss_welcome_modal_if_present()
        self.press(link)
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

    def log_in_if_locked(self, username: str, password: str) -> None:
        """Open the lock-screen login and sign in when access control is on.

        The logged-out dialog covers the whole touchscreen, so nav clicks never
        land until this returns.
        """
        self.dismiss_canceled_run_if_present()
        overlay = self.page.get_by_role("dialog", name="Logged out")
        username_input = self.page.locator('input[name="username"]')
        password_input = self.page.locator('input[name="password"]')
        overlay_open = overlay.count() > 0 and overlay.is_visible()
        username_open = username_input.count() > 0 and username_input.is_visible()
        password_open = password_input.count() > 0 and password_input.is_visible()
        if not overlay_open and not username_open and not password_open:
            return
        if overlay_open:
            # A pointer click is swallowed on the way to this overlay. A DOM click
            # still reaches the React handler that opens the login screen.
            overlay.dispatch_event("click")
        primary = self.page.get_by_test_id("ChildNavigation_Primary_Button").last
        if not password_open:
            expect(username_input).to_be_visible(timeout=15_000)
            username_input.fill(username)
            primary.dispatch_event("click")
        expect(password_input).to_be_visible(timeout=15_000)
        password_input.fill(password)
        primary.dispatch_event("click")
        expect(overlay).to_have_count(0, timeout=15_000)
        expect(password_input).to_have_count(0, timeout=15_000)

    def open_settings(self) -> None:
        """Open Robot Settings from the top nav."""
        self._follow(self.settings_nav, self.SETTINGS_URL)

    def open_kebab(self) -> None:
        """Open the overflow menu and wait until Home gantry is visible."""
        self.dismiss_welcome_modal_if_present()
        expect(self.kebab_nav).to_be_visible(timeout=15_000)
        self.kebab_nav.click()
        expect(self.page.get_by_role("button", name="Home gantry")).to_be_visible(timeout=10_000)

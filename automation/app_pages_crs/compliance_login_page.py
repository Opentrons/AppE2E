"""Compliance Ready Software login on the desktop robot detail page.

``DevicesPage`` opens the robot. This page starts after that detail view is showing.
"""

from __future__ import annotations

from typing import Self

from playwright.sync_api import Locator, Page, expect

from automation.app_helpers.crs_accounts import CrsAccount
from automation.app_helpers.locator_helpers import exact_text
from automation.app_pages.base_app.app_base_page import AppBasePage


class ComplianceLoginPage(AppBasePage):
    """Log-in modal and signed-in account button on a robot detail page."""

    LOGIN_TITLE = "Compliance Ready Software login"

    def __init__(self, page: Page, *, username: str) -> None:
        """Bind the page and the account whose initial is shown after login."""
        super().__init__(page)
        self.username = username

    @classmethod
    def from_account(cls, page: Page, account: CrsAccount) -> Self:
        """Build a page object bound to ``account``'s username initial."""
        return cls(page, username=account.username)

    @property
    def account_initial(self) -> str:
        """Letter on the signed-in account button."""
        return self.username[:1].upper()

    @property
    def log_in_button(self) -> Locator:
        """Top-right Log in control on the robot detail breadcrumbs."""
        return self.page.get_by_test_id("basic_button_Log in")

    @property
    def login_title(self) -> Locator:
        """Heading of the Compliance Ready login modal."""
        return self.page.get_by_text(exact_text(self.LOGIN_TITLE))

    @property
    def username_input(self) -> Locator:
        """Username field. Fill the lab account from ``CrsAccount``."""
        return self.page.locator('input[name="username"]')

    @property
    def password_input(self) -> Locator:
        """Password field. Fill the lab account from ``CrsAccount``."""
        return self.page.locator('input[name="password"]')

    @property
    def submit_button(self) -> Locator:
        """Submit control inside the login modal."""
        return self.page.locator('button[type="submit"]').filter(has_text="Log in")

    @property
    def account_popover(self) -> Locator:
        """Top-right signed-in account chrome (CSS-module class substring is stable)."""
        return self.page.locator('[class*="account_popover_menu_container"]')

    @property
    def account_button(self) -> Locator:
        """Top-right signed-in account icon inside the account popover."""
        return self.account_popover.get_by_role("button", name=exact_text(self.account_initial))

    @property
    def header_account_button(self) -> Locator:
        """Whoever is signed in — the button inside the account popover."""
        return self.account_popover.get_by_role("button")

    @property
    def account_menu(self) -> Locator:
        """Account overflow menu (Account settings / Log out)."""
        return self.page.get_by_test_id("MenuList")

    @property
    def log_out_menu_item(self) -> Locator:
        """Log out control inside the open account menu."""
        return self.account_menu.get_by_role("button", name=exact_text("Log out"))

    def access_control_is_on(self) -> bool:
        """True when this robot shows a Log in button or a signed-in account."""
        chrome = self.log_in_button.or_(self.account_popover)
        try:
            expect(chrome.first).to_be_visible(timeout=5_000)
        except AssertionError:
            return False
        return True

    def is_logged_in(self) -> bool:
        """True when this account's initial is shown and Log in is gone."""
        return (
            self.log_in_button.count() == 0
            and self.account_button.count() > 0
            and self.account_button.is_visible()
        )

    def ensure_logged_out(self) -> None:
        """Log out whoever is signed in, or no-op when Log in is already showing."""
        if self.log_in_button.count() > 0 and self.log_in_button.is_visible():
            return
        expect(self.header_account_button.first).to_be_visible()
        self._log_out_from(self.header_account_button.first)

    def log_in(self, username: str, password: str) -> None:
        """Open the login modal, submit the account, and require the account button."""
        self.username = username
        self.ensure_logged_out()
        self.log_in_button.click()
        expect(self.login_title).to_be_visible()
        expect(self.username_input).to_be_visible()
        expect(self.password_input).to_be_visible()
        self.username_input.fill(username)
        self.password_input.fill(password)
        self.submit_button.click()
        self.expect_logged_in()

    def log_in_as(self, account: CrsAccount) -> None:
        """Sign in as ``account`` and require that account's initial button."""
        self.log_in(account.username, account.password)

    def ensure_logged_in_as(self, account: CrsAccount) -> None:
        """Sign in as ``account`` unless that account's button is already showing."""
        self.username = account.username
        if self.is_logged_in():
            return
        self.log_in_as(account)

    def log_out(self) -> None:
        """Open the top-right account menu and sign out of this user."""
        expect(self.account_button).to_be_visible()
        self._log_out_from(self.account_button)

    def _log_out_from(self, account_button: Locator) -> None:
        """Open the account menu, choose Log out, wait for Log in."""
        self._open_account_menu(account_button)
        self._click_log_out()
        self.expect_logged_out()

    def _open_account_menu(self, account_button: Locator) -> None:
        """Open the account overflow menu; do not toggle it closed if already open."""
        if self.account_menu.count() == 0 or not self.account_menu.is_visible():
            account_button.click()
        expect(self.account_menu).to_be_visible(timeout=10_000)
        expect(self.log_out_menu_item).to_be_visible(timeout=10_000)

    def _click_log_out(self) -> None:
        """Activate Log out inside the open account menu via the DOM node.

        The desktop ``MenuList`` is often visually offset, so a pointer click can
        miss and only dismiss the menu. Calling ``click()`` on the button node
        runs the React handler without hit-testing.
        """
        expect(self.log_out_menu_item).to_be_visible()
        self.log_out_menu_item.evaluate("button => button.click()")

    def expect_logged_in(self) -> None:
        """Require the login form to be gone and the account button to be visible."""
        expect(self.username_input).to_be_hidden()
        expect(self.log_in_button).to_have_count(0)
        expect(self.account_button).to_be_visible()

    def expect_logged_out(self) -> None:
        """Require the account popover gone and top-right Log in visible.

        Do not match single-letter buttons page-wide — deck slots are also A–Z.
        """
        expect(self.account_popover).to_have_count(0, timeout=15_000)
        expect(self.log_in_button).to_be_visible(timeout=15_000)

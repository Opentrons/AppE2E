"""Compliance Ready Software login on the desktop robot detail page.

``DevicesPage`` opens the robot. This page starts after that detail view is showing.
"""

from __future__ import annotations

from playwright.sync_api import Locator, Page, expect

from automation.app_pages.base_app.app_base_page import AppBasePage


class ComplianceLoginPage(AppBasePage):
    """Log-in modal and signed-in account button on a robot detail page."""

    LOGIN_TITLE = "Compliance Ready Software login"

    def __init__(self, page: Page, *, username: str) -> None:
        """Bind the page and the account whose initial is shown after login."""
        super().__init__(page)
        self.username = username

    @property
    def account_initial(self) -> str:
        """Letter on the signed-in account button."""
        return self.username[:1].upper()

    @property
    def log_in_button(self) -> Locator:
        """Robot-detail button that opens the login modal."""
        return self.page.get_by_role("button", name="Log in", exact=True)

    @property
    def login_title(self) -> Locator:
        """Heading of the Compliance Ready login modal."""
        return self.page.get_by_text(self.LOGIN_TITLE, exact=True)

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
    def account_button(self) -> Locator:
        """Signed-in account button, labeled with the username initial."""
        return self.page.get_by_role("button", name=self.account_initial, exact=True)

    def access_control_is_on(self) -> bool:
        """True when this robot shows a Log in button or a signed-in account."""
        chrome = self.log_in_button.or_(self.account_button)
        try:
            expect(chrome.first).to_be_visible(timeout=5_000)
        except AssertionError:
            return False
        return True

    def is_logged_in(self) -> bool:
        """True when the account initial is shown and Log in is gone."""
        log_in = self.log_in_button
        account = self.account_button
        return log_in.count() == 0 and account.count() > 0 and account.is_visible()

    def log_in(self, username: str, password: str) -> None:
        """Open the login modal, submit the account, and require the account button."""
        self.log_in_button.click()
        expect(self.login_title).to_be_visible()
        expect(self.username_input).to_be_visible()
        expect(self.password_input).to_be_visible()
        self.username_input.fill(username)
        self.password_input.fill(password)
        self.submit_button.click()
        self.expect_logged_in()

    def expect_logged_in(self) -> None:
        """Require the login form to be gone and the account button to be visible."""
        expect(self.username_input).to_be_hidden()
        expect(self.log_in_button).to_have_count(0)
        expect(self.account_button).to_be_visible()

"""Compliance Ready → User management on Robot Settings.

Admin can expand User management, create accounts, and read the one-time
password modal. A non-admin signed-in user only sees Personal account settings.
"""

from __future__ import annotations

from playwright.sync_api import Locator, Page, expect

from automation.app_helpers.locator_helpers import exact_text
from automation.app_pages.base_app.app_base_page import AppBasePage
from automation.app_pages.base_app.robot_settings_page import RobotSettingsPage
from automation.app_pages_crs.documentation_required_page import AppDocumentationRequired


class UserManagementPage(AppBasePage):
    """User management accordion and Add user wizard on Compliance Ready."""

    PERSONAL_ACCOUNT = "Personal account settings"
    USER_MANAGEMENT = "User management"
    ADD_USER = "Add user"
    CREATE_ACCOUNT = "Create account"
    ONE_TIME_PASSWORD = "One-time password"
    ROLE_USER = "User"
    ROLE_ADMIN = "Admin"

    def __init__(self, page: Page, *, robot_name: str) -> None:
        """Bind the page and robot whose Compliance Ready tab we drive."""
        super().__init__(page)
        self.robot_name = robot_name

    @property
    def dialog(self) -> Locator:
        """Add-user / one-time-password modal shell."""
        return self.page.get_by_role("dialog", name="ModalShell_ModalArea")

    @property
    def personal_account_heading(self) -> Locator:
        """Personal account settings section title (any signed-in role)."""
        return self.page.get_by_text(exact_text(self.PERSONAL_ACCOUNT))

    @property
    def user_management_accordion(self) -> Locator:
        """User management accordion header (admins only)."""
        return self.page.get_by_role("button", name=exact_text(self.USER_MANAGEMENT))

    @property
    def add_user_button(self) -> Locator:
        """Add user control inside the expanded accordion (``EmptySelectorButton``)."""
        return self.page.get_by_role("button", name=exact_text(self.ADD_USER))

    def user_row_overflow(self, username: str) -> Locator:
        """Overflow trigger for ``username`` in the management table."""
        return self.page.get_by_role("button", name=exact_text(f"UserManagement_overflowMenu_{username}"))

    def open(self) -> None:
        """Open Robot Settings → Compliance Ready."""
        RobotSettingsPage(self.page, robot_name=self.robot_name).navigate(
            tab=("Compliance Ready", "compliance-ready")
        )
        expect(self.personal_account_heading).to_be_visible()

    def expand_user_management(self) -> None:
        """Expand the User management accordion until Add user is visible."""
        accordion = self.user_management_accordion
        expect(accordion).to_be_visible()
        if accordion.get_attribute("aria-expanded") != "true":
            accordion.click()
        expect(self.add_user_button).to_be_visible()

    def expect_user_management_hidden(self) -> None:
        """Require User management to be absent (non-admin roles)."""
        expect(self.user_management_accordion).to_have_count(0)

    def expect_personal_account(self, *, username: str, legal_name: str) -> None:
        """Require Personal account settings to show ``username`` and ``legal_name``."""
        expect(self.personal_account_heading).to_be_visible()
        expect(self.page.get_by_text(exact_text(username))).to_be_visible()
        expect(self.page.get_by_text(exact_text(legal_name))).to_be_visible()
        expect(self.page.get_by_test_id("basic_button_Edit")).to_be_visible()

    def create_user(
        self,
        *,
        username: str,
        legal_name: str,
        role: str = ROLE_USER,
        note: str = "e2e creating user",
    ) -> str:
        """Add a user, confirm documentation, and return the one-time password.

        ``role`` is the visible label (User / Admin / Auditor). Default is User;
        the form itself defaults to Admin, so the role menu is always opened.
        """
        self.expand_user_management()
        self.add_user_button.click()
        expect(self.dialog.get_by_text(exact_text(self.CREATE_ACCOUNT)).first).to_be_visible()

        self._identity_field("Username").fill(username)
        self._identity_field("Legal name").fill(legal_name)
        self._select_role(role)

        self.dialog.get_by_role("button", name=exact_text(self.CREATE_ACCOUNT)).click()
        AppDocumentationRequired(self.page).confirm_note(note)

        otp = self._read_one_time_password()
        self.dialog.get_by_role("button", name=exact_text("Confirm")).click()
        expect(self.dialog).to_be_hidden()
        expect(self.user_row_overflow(username)).to_be_visible()
        return otp

    def _identity_field(self, label: str) -> Locator:
        """Username / Legal name textbox beside its label in the Add user form.

        These ``InputField``s do not set an accessible name; the label is a sibling.
        """
        field = (
            self.dialog.get_by_text(exact_text(label))
            .locator("xpath=following-sibling::*[1]")
            .get_by_role("textbox")
        )
        expect(field).to_be_visible()
        return field

    def _select_role(self, role: str) -> None:
        """Open the Role dropdown and choose ``role``.

        Options live in a ``listbox`` (not page-wide buttons), so we avoid matching
        other ``User`` / ``Admin`` chrome on the management table.
        """
        self.dialog.get_by_test_id("dropdownMenu").click()
        option = self.page.get_by_role("listbox").get_by_role("button", name=exact_text(role))
        expect(option).to_be_visible()
        option.click()
        expect(self.dialog.get_by_test_id("dropdownMenu")).to_contain_text(role)

    def _read_one_time_password(self) -> str:
        """Read the generated password from the success step of Add user."""
        expect(self.dialog.get_by_text(exact_text(self.ONE_TIME_PASSWORD)).first).to_be_visible()
        value = self.dialog.locator('[class*="one_time_password_value"]')
        expect(value).to_be_visible()
        otp = value.inner_text().strip()
        if not otp:
            raise AssertionError("Add user did not show a one-time password.")
        return otp

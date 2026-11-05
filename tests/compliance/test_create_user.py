"""Create a User-role account, then open Compliance Ready as that user.

Admin creates the account under User management, captures the one-time
password, logs out, completes first-login password setup, and verifies the
new user only sees Personal account settings (not User management). The new
account is merged into **Compliance Ready accounts** for later User login tests.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from playwright.sync_api import Page

from automation.app_helpers.crs_accounts import CrsAccount, CrsReportedAccount, report_crs_account
from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages_crs import ComplianceLoginPage, UserManagementPage

_LOGIN_ADMIN = "tests/compliance/test_login.py::test_login_admin"


@pytest.mark.dismiss_blockers
@pytest.mark.workflow(
    group="compliance_testing",
    section="Admin",
    label="Create user and open Compliance Ready as that user",
    order=40,
    requires=_LOGIN_ADMIN,
)
def test_create_user_views_compliance_ready(
    crs_logged_in: Page,
    robot_name: str,
    crs_user: CrsAccount,
) -> None:
    """Admin creates a User; that user signs in and opens Compliance Ready."""
    page = crs_logged_in
    users = UserManagementPage(page, robot_name=robot_name)
    # Unique each run so a leftover account from a prior attempt does not collide.
    username = f"user{uuid4().hex[:6]}"
    legal_name = "user jones"
    new_password = "newuser!"
    new_account = CrsAccount(
        username=username,
        password=new_password,
        legal_name=legal_name,
        role="User",
    )

    log_step("Open Compliance Ready → User management")
    users.open()
    users.expand_user_management()
    log_done("User management is expanded")

    log_step(f"Create User-role account {username!r}")
    otp = users.create_user(
        username=username,
        legal_name=legal_name,
        role=UserManagementPage.ROLE_USER,
        note="e2e creating user",
    )
    log_done(f"Account created; one-time password captured ({len(otp)} chars)")

    log_step(f"Log out of Admin ({crs_user.username!r})")
    ComplianceLoginPage.from_account(page, crs_user).log_out()
    log_done("Logged out")

    login = ComplianceLoginPage.from_account(page, new_account)
    log_step(f"First login as {username!r} with one-time password")
    login.log_in_with_one_time_password(username, otp)
    login.set_new_password(new_password, note="e2e new user password")
    login.log_in_as(new_account)
    log_done(f"Signed in as {username!r} (account button {new_account.account_initial!r})")

    log_step("Record User in Compliance Ready accounts")
    report_crs_account(
        CrsReportedAccount(
            role="User",
            username=username,
            password=new_password,
            legal_name=legal_name,
        )
    )
    log_done(f"User {username!r} saved for later login tests")

    log_step("Open Compliance Ready as the new user")
    users.open()
    users.expect_personal_account(username=username, legal_name=legal_name)
    users.expect_user_management_hidden()
    log_done("Personal account settings visible; User management hidden for User role")

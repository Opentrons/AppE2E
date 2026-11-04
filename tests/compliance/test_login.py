"""Log in / log out once per Compliance Ready account type.

Each account is a section under **Compliance Ready Testing** (Service / Admin /
User / Recovery). Log in opens the lane; Log out closes it (order leaves room
for workflows in between). Passwords come from ``artifacts/crs_accounts.json``.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from automation.app_helpers.crs_accounts import CrsAccount
from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages_crs import ComplianceLoginPage

_LOGIN_SERVICE = "tests/compliance/test_login.py::test_login_service"
_LOGIN_ADMIN = "tests/compliance/test_login.py::test_login_admin"
_LOGIN_USER = "tests/compliance/test_login.py::test_login_user"
_LOGIN_RECOVERY = "tests/compliance/test_login.py::test_login_recovery"


@pytest.mark.workflow(
    group="compliance_testing",
    section="Service",
    label="Log in as Service",
    order=20,
)
def test_login_service(crs_enabled: Page, crs_service_user: CrsAccount) -> None:
    """Sign in as Service."""
    log_step(f"Log in as Service ({crs_service_user.username!r})")
    ComplianceLoginPage.from_account(crs_enabled, crs_service_user).log_in_as(crs_service_user)
    log_done(f"Service account button {crs_service_user.account_initial!r} is visible")


@pytest.mark.workflow(
    group="compliance_testing",
    section="Service",
    label="Log out of Service",
    order=90,
    requires=_LOGIN_SERVICE,
)
def test_logout_service(crs_enabled: Page, crs_service_user: CrsAccount) -> None:
    """Sign out of Service."""
    login = ComplianceLoginPage.from_account(crs_enabled, crs_service_user)
    log_step(f"Log out of Service ({crs_service_user.username!r})")
    login.ensure_logged_in_as(crs_service_user)
    login.log_out()
    log_done("Log in is visible again")


@pytest.mark.workflow(
    group="compliance_testing",
    section="Admin",
    label="Log in as Admin",
    order=30,
)
def test_login_admin(crs_enabled: Page, crs_user: CrsAccount) -> None:
    """Sign in as Admin."""
    log_step(f"Log in as Admin ({crs_user.username!r})")
    ComplianceLoginPage.from_account(crs_enabled, crs_user).log_in_as(crs_user)
    log_done(f"Admin account button {crs_user.account_initial!r} is visible")


@pytest.mark.workflow(
    group="compliance_testing",
    section="Admin",
    label="Log out of Admin",
    order=90,
    requires=_LOGIN_ADMIN,
)
def test_logout_admin(crs_enabled: Page, crs_user: CrsAccount) -> None:
    """Sign out of Admin."""
    login = ComplianceLoginPage.from_account(crs_enabled, crs_user)
    log_step(f"Log out of Admin ({crs_user.username!r})")
    login.ensure_logged_in_as(crs_user)
    login.log_out()
    log_done("Log in is visible again")


@pytest.mark.workflow(
    group="compliance_testing",
    section="User",
    label="Log in as User",
    order=50,
)
def test_login_user(crs_enabled: Page, crs_standard_user: CrsAccount) -> None:
    """Sign in as User."""
    log_step(f"Log in as User ({crs_standard_user.username!r})")
    ComplianceLoginPage.from_account(crs_enabled, crs_standard_user).log_in_as(crs_standard_user)
    log_done(f"User account button {crs_standard_user.account_initial!r} is visible")


@pytest.mark.workflow(
    group="compliance_testing",
    section="User",
    label="Log out of User",
    order=90,
    requires=_LOGIN_USER,
)
def test_logout_user(crs_enabled: Page, crs_standard_user: CrsAccount) -> None:
    """Sign out of User."""
    login = ComplianceLoginPage.from_account(crs_enabled, crs_standard_user)
    log_step(f"Log out of User ({crs_standard_user.username!r})")
    login.ensure_logged_in_as(crs_standard_user)
    login.log_out()
    log_done("Log in is visible again")


@pytest.mark.workflow(
    group="compliance_testing",
    section="Recovery",
    label="Log in as Recovery",
    order=60,
)
def test_login_recovery(crs_enabled: Page, crs_recovery_user: CrsAccount) -> None:
    """Sign in as Recovery."""
    log_step(f"Log in as Recovery ({crs_recovery_user.username!r})")
    ComplianceLoginPage.from_account(crs_enabled, crs_recovery_user).log_in_as(crs_recovery_user)
    log_done(f"Recovery account button {crs_recovery_user.account_initial!r} is visible")


@pytest.mark.workflow(
    group="compliance_testing",
    section="Recovery",
    label="Log out of Recovery",
    order=90,
    requires=_LOGIN_RECOVERY,
)
def test_logout_recovery(crs_enabled: Page, crs_recovery_user: CrsAccount) -> None:
    """Sign out of Recovery."""
    login = ComplianceLoginPage.from_account(crs_enabled, crs_recovery_user)
    log_step(f"Log out of Recovery ({crs_recovery_user.username!r})")
    login.ensure_logged_in_as(crs_recovery_user)
    login.log_out()
    log_done("Log in is visible again")

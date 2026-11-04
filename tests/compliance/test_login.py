"""Log in once per Compliance Ready account type.

Each case is its own workflow section header (Service / Admin / Recovery) so
later account-specific workflows can group under the matching section.
Passwords come from ``artifacts/crs_accounts.json`` written by Enable CRS.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from automation.app_helpers.crs_accounts import CrsAccount
from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages_crs import ComplianceLoginPage


@pytest.mark.workflow(
    group="compliance",
    section="Service",
    label="Log in",
    order=20,
)
def test_login_service(crs_enabled: Page, crs_service_user: CrsAccount) -> None:
    """Sign in as Service."""
    log_step(f"Log in as Service ({crs_service_user.username!r})")
    ComplianceLoginPage.from_account(crs_enabled, crs_service_user).log_in_as(crs_service_user)
    log_done(f"Service account button {crs_service_user.account_initial!r} is visible")


@pytest.mark.workflow(
    group="compliance",
    section="Admin",
    label="Log in",
    order=30,
)
def test_login_admin(crs_enabled: Page, crs_user: CrsAccount) -> None:
    """Sign in as Admin."""
    log_step(f"Log in as Admin ({crs_user.username!r})")
    ComplianceLoginPage.from_account(crs_enabled, crs_user).log_in_as(crs_user)
    log_done(f"Admin account button {crs_user.account_initial!r} is visible")


@pytest.mark.workflow(
    group="compliance",
    section="Recovery",
    label="Log in",
    order=40,
)
def test_login_recovery(crs_enabled: Page, crs_recovery_user: CrsAccount) -> None:
    """Sign in as Recovery."""
    log_step(f"Log in as Recovery ({crs_recovery_user.username!r})")
    ComplianceLoginPage.from_account(crs_enabled, crs_recovery_user).log_in_as(crs_recovery_user)
    log_done(f"Recovery account button {crs_recovery_user.account_initial!r} is visible")

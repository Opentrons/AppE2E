"""Compliance Ready login smoke — Devices > robot > Log in."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from automation.app_helpers.crs_accounts import CrsAccount
from automation.app_pages import ComplianceLoginPage


@pytest.mark.workflow(
    group="compliance",
    section="Login",
    label="Log in as the lab admin",
    order=20,
)
def test_example(crs_logged_in: Page, crs_user: CrsAccount) -> None:
    """Require the signed-in account button on the robot detail page."""
    ComplianceLoginPage(crs_logged_in, username=crs_user.username).expect_logged_in()

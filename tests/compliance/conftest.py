"""Compliance Ready fixtures for the desktop app."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from automation.app_helpers.crs_accounts import CrsAccount, load_crs_account
from automation.app_helpers.test_progress import log_done, log_info, log_step
from automation.app_pages import ComplianceLoginPage, DevicesPage

# Pull in run_local_app / playwright launch from tests/app/conftest.py
pytest_plugins = ["tests.app.conftest"]

# Playwright Inspector recorder; it pauses until closed, so it is not a CRS check.
_UNMARKED = {"example_test.py"}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Tag Compliance Ready tests so ``pytest -m crs`` selects them."""
    marker = pytest.mark.crs
    for item in items:
        nodeid = item.nodeid.replace("\\", "/")
        if "/compliance/" not in nodeid or item.path.name in _UNMARKED:
            continue
        if item.get_closest_marker("crs") is None:
            item.add_marker(marker)


@pytest.fixture
def crs_user() -> CrsAccount:
    """Lab account for Compliance Ready login. Defaults live in ``crs_accounts``."""
    return load_crs_account()


@pytest.fixture
def crs_enabled(run_local_app: Page, robot_name: str, crs_user: CrsAccount) -> Page:
    """Open the robot detail page and skip when Compliance Ready is off."""
    log_step(f"Open Devices > {robot_name}")
    DevicesPage(run_local_app, robot_name=robot_name).navigate()
    log_done(f"On {robot_name} detail")
    login = ComplianceLoginPage(run_local_app, username=crs_user.username)
    if not login.access_control_is_on():
        pytest.skip(f"Compliance Ready is not enabled on {robot_name}")
    return run_local_app


@pytest.fixture
def crs_logged_in(crs_enabled: Page, robot_name: str, crs_user: CrsAccount) -> Page:
    """Sign in on the robot detail page when the account button is not showing."""
    login = ComplianceLoginPage(crs_enabled, username=crs_user.username)
    if login.is_logged_in():
        log_info(
            f"Already logged in to {robot_name} as {crs_user.username!r} "
            f"(account button {crs_user.account_initial!r} visible; skipping login)."
        )
        return crs_enabled
    log_step(f"Log in to {robot_name} as {crs_user.username!r}")
    login.log_in(crs_user.username, crs_user.password)
    log_done("Logged in")
    return crs_enabled

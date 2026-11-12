"""Admin login for the CRS app suite.

Tests under ``admin_walk/`` (including mirrored ``admin_walk/crs_app/`` copies of
``tests/app``) carry ``crs_login`` and use a logged-in ``run_local_app``.
"""

from __future__ import annotations

from typing import Any

import pytest
from _pytest.python import Function
from playwright.sync_api import Page

from automation.app_helpers.app_readiness import crs_gate_is_visible
from automation.app_helpers.crs_accounts import load_crs_account
from automation.app_helpers.locator_helpers import exact_text
from automation.app_helpers.test_progress import log_done, log_info, log_step
from automation.app_pages import DevicesPage
from automation.app_pages_crs import ComplianceLoginPage, WriteDocumentation
from automation.app_pages_crs.write_documentation import install_documentation_fallback


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark every admin-walk case as CRS Admin (logged-in) with toast dismiss."""
    crs_login = pytest.mark.crs_login
    dismiss = pytest.mark.dismiss_blockers
    for item in items:
        nodeid = item.nodeid.replace("\\", "/")
        if "/admin_walk/" not in nodeid:
            continue
        if item.get_closest_marker("crs_login") is None:
            item.add_marker(crs_login)
        if item.get_closest_marker("no_dismiss_blockers") is not None:
            continue
        if item.get_closest_marker("dismiss_blockers") is None:
            item.add_marker(dismiss)


@pytest.fixture(scope="session")
def crs_admin_login(electron_page: Page, robot_name: str) -> Page:
    """Open the robot and sign in as Admin once for this pytest session."""
    account = load_crs_account()
    log_step(f"Open Devices > {robot_name}")
    DevicesPage(electron_page, robot_name=robot_name).navigate()
    log_done(f"On {robot_name} detail")
    login = ComplianceLoginPage.from_account(electron_page, account)
    if not login.access_control_is_on():
        pytest.skip(f"Compliance Ready is not enabled on {robot_name}")
    if login.is_logged_in():
        log_info(
            f"Already logged in to {robot_name} as {account.username!r} "
            f"(account button {account.account_initial!r} visible; skipping login)."
        )
        return electron_page
    log_step(f"Log in to {robot_name} as {account.username!r}")
    login.log_in_as(account)
    log_done("Logged in as Admin")
    return electron_page


@pytest.fixture(scope="session")
def run_local_app(crs_admin_login: Page) -> Page:
    """Logged-in app page for CRS admin-walk tests (overrides session logged-out alias)."""
    return crs_admin_login


@pytest.fixture
def write_documentation(run_local_app: Page) -> WriteDocumentation:
    """Read the Action list, type that text, and confirm Documentation required."""
    return WriteDocumentation(run_local_app)


@pytest.fixture(autouse=True)
def _recover_documentation_required(
    request: pytest.FixtureRequest,
    run_local_app: Page,
) -> Any:
    """CRS tests confirm Documentation required when a click opens or is blocked by it."""
    if request.node.get_closest_marker("crs_login") is None:
        yield
        return
    WriteDocumentation.clear_recorded(run_local_app)
    with install_documentation_fallback(run_local_app):
        yield


def _heading_visible(page: Page, title: str) -> bool:
    heading = page.get_by_text(exact_text(title))
    try:
        return heading.count() > 0 and heading.first.is_visible()
    except Exception:
        return False


def _classify(page: Page | None) -> str:
    """One line for the admin walk: what stopped this CRS case."""
    if page is None:
        return "failed for another reason"
    if _heading_visible(page, "Documentation required"):
        return "blocked by Documentation required"
    if _heading_visible(page, "Compliance Ready Software login"):
        return "blocked by login"
    try:
        log_in = page.get_by_test_id("basic_button_Log in")
        if log_in.count() > 0 and log_in.first.is_visible():
            return "blocked by login"
    except Exception:
        pass
    if crs_gate_is_visible(page):
        return "blocked by Documentation required"
    return "failed for another reason"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[Any]) -> Any:
    """Log pass, login block, documentation block, or another failure for crs_login tests."""
    outcome = yield
    report = outcome.get_result()
    if item.get_closest_marker("crs_login") is None:
        return
    if report.when == "setup" and report.passed:
        return
    if report.when == "teardown":
        return
    if report.when == "call" and report.passed:
        log_info(f"admin-walk {item.nodeid}: passed")
        return
    if report.skipped:
        log_info(f"admin-walk {item.nodeid}: skipped")
        return
    if not report.failed:
        return
    funcargs = item.funcargs if isinstance(item, Function) else {}
    page = funcargs.get("crs_admin_login") or funcargs.get("run_local_app")
    if not isinstance(page, Page):
        page = None
    log_info(f"admin-walk {item.nodeid}: {_classify(page)}")

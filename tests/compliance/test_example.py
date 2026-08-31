"""Compliance Ready login smoke — Devices > robot > Log in."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from automation.app_helpers.test_progress import log_done, log_info, log_step
from automation.app_pages import DevicesPage

ROBOT_NAME = "QA2PVT"
USERNAME = "testadmin"
PASSWORD = "testadminpassword"
ACCOUNT_INITIAL = USERNAME[0].upper()
ALREADY_LOGGED_IN_MSG = (
    f"Already logged in to {ROBOT_NAME} as {USERNAME!r} "
    f"(account button {ACCOUNT_INITIAL!r} visible; skipping login)."
)


def _is_logged_in(page: Page) -> bool:
    """True when the account initial is shown and Log in is gone."""
    log_in = page.get_by_role("button", name="Log in", exact=True)
    account = page.get_by_role("button", name=ACCOUNT_INITIAL, exact=True)
    return log_in.count() == 0 and account.count() > 0 and account.is_visible()


def test_example(run_local_app: Page) -> None:
    """Log in to Compliance Ready Software on the robot detail page."""
    page = run_local_app

    log_step(f"Open Devices > {ROBOT_NAME}")
    DevicesPage(page, robot_name=ROBOT_NAME).navigate()
    log_done(f"On {ROBOT_NAME} detail")

    if _is_logged_in(page):
        log_info(ALREADY_LOGGED_IN_MSG)
        return

    log_step("Open Compliance Ready login modal")
    page.get_by_role("button", name="Log in", exact=True).click()
    expect(page.get_by_text("Compliance Ready Software login", exact=True)).to_be_visible()
    expect(page.locator('input[name="username"]')).to_be_visible()
    expect(page.locator('input[name="password"]')).to_be_visible()

    log_step(f"Fill username={USERNAME!r} and password")
    page.locator('input[name="username"]').fill(USERNAME)
    page.locator('input[name="password"]').fill(PASSWORD)

    log_step("Submit Log in")
    page.locator('button[type="submit"]').filter(has_text="Log in").click()

    expect(page.locator('input[name="username"]')).to_be_hidden()
    expect(page.get_by_role("button", name="Log in", exact=True)).to_have_count(0)
    expect(page.get_by_role("button", name=ACCOUNT_INITIAL, exact=True)).to_be_visible()
    log_done("Logged in")

"""Blow out a pipette tip into the waste chute, drop the tip there, and exit."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages.odd import OddInstrumentsPage

# Same lab account as the Robot Settings login.
_USERNAME = "testadmin"
_PASSWORD = "testadminpassword"


def _drop_tip_wizard_is_open(page: Page) -> bool:
    """True when a previous Drop tips attempt is still on screen."""
    open_wizard = (
        page.get_by_text("Documentation required", exact=True)
        .or_(page.get_by_text(re.compile(r"^Getting ready")))
        .or_(page.get_by_text("Before you begin, do you need to preserve aspirated liquid?"))
    )
    return open_wizard.count() > 0 and open_wizard.first.is_visible()


@pytest.mark.odd
@pytest.mark.timeout(540)
@pytest.mark.workflow(
    group="odd_instruments",
    section="Drop tips",
    label="Blow out and drop tip in waste chute",
    order=10,
)
def test_odd_blowout_and_drop_tip_in_waste_chute(run_odd_app: Page) -> None:
    """Open the left pipette and run blowout → waste-chute drop → Exit.

    The gantry moves. The robot door must be closed, and a waste chute must
    be configured on the deck.
    """
    page = run_odd_app
    instruments = OddInstrumentsPage(page)

    log_step("Sign in when the touchscreen is locked")
    instruments.log_in_if_locked(_USERNAME, _PASSWORD)
    log_done("Touchscreen is unlocked")

    if _drop_tip_wizard_is_open(page):
        log_step("Drop tips wizard is already open")
    elif re.search(r"/instruments/(left|right)\b", page.url):
        log_step("Pipette detail is already open")
        log_done(page.url)
    else:
        log_step("Open the left pipette")
        instruments.open()
        instruments.open_mount("left")
        log_done("Pipette detail open")

    log_step("Blow out and drop the tip in the waste chute")
    instruments.drop_tips_in_waste_chute()
    log_done("Tip drop wizard exited")


@pytest.mark.odd
@pytest.mark.timeout(540)
@pytest.mark.workflow(
    group="odd_instruments",
    section="Drop tips",
    label="Drop tip in waste chute without blowout",
    order=20,
)
def test_odd_drop_tip_in_waste_chute_without_blowout(run_odd_app: Page) -> None:
    """Skip blowout with "No, proceed to tip removal", then drop in the waste chute."""
    page = run_odd_app
    instruments = OddInstrumentsPage(page)

    log_step("Sign in when the touchscreen is locked")
    instruments.log_in_if_locked(_USERNAME, _PASSWORD)
    log_done("Touchscreen is unlocked")

    if _drop_tip_wizard_is_open(page):
        log_step("Drop tips wizard is already open")
    elif re.search(r"/instruments/(left|right)\b", page.url):
        log_step("Pipette detail is already open")
        log_done(page.url)
    else:
        log_step("Open the left pipette")
        instruments.open()
        instruments.open_mount("left")
        log_done("Pipette detail open")

    log_step("Skip blowout and drop the tip in the waste chute")
    instruments.drop_tips_without_blowout()
    log_done("Tip drop wizard exited without blowout")

"""ODD deck configuration: add a waste chute on D3."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages.odd import OddDeckConfigurationPage

# Same lab account as the other ODD flows.
_USERNAME = "testadmin"
_PASSWORD = "testadminpassword"


@pytest.mark.odd
@pytest.mark.workflow(
    group="odd_deck",
    section="Deck configuration",
    label="Configure standard QA deck with waste chute",
    order=10,
    cases=(
        ("C44952", "Deck Configuration"),
        ("C44951", "Deck Configuration"),
    ),
)
def test_odd_deck_configuration(run_odd_app: Page) -> None:
    """Open Deck configuration and load the standard QA lab layout, including a waste chute.

    C44952 Deck Configuration and C44951 Deck Configuration.
    Deck-conflict cases C44759 (heater-shaker) and C44760 (modules in staging) are not covered.
    """
    page = run_odd_app
    deck = OddDeckConfigurationPage(page)

    log_step("Sign in when the touchscreen is locked")
    deck.log_in_if_locked(_USERNAME, _PASSWORD)
    log_done("Touchscreen is unlocked")

    log_step("Open Deck configuration")
    deck.open()
    log_done("Deck configuration is open")

    log_step("Add the standard lab modules and a waste chute")
    added = deck.configure_standard_deck()
    log_done(f"Deck configured — added {added}")

    log_step("Save")
    deck.save()
    log_done("Deck configuration saved")

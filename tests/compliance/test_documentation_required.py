"""Parked checks for the desktop Documentation required screen.

Each test names the ``AppDocumentationRequired`` method to fill in from the
live screen. They stay skipped until that method submits the note or opens
View actions.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from automation.app_pages import AppDocumentationRequired


@pytest.mark.skip(reason="Fill in AppDocumentationRequired.submit_empty_note from the live desktop screen")
def test_empty_note_is_rejected(crs_logged_in: Page) -> None:
    """A blank note stays on Documentation required."""
    AppDocumentationRequired(crs_logged_in).submit_empty_note()


@pytest.mark.skip(reason="Fill in AppDocumentationRequired.submit_short_note from the live desktop screen")
def test_short_note_is_rejected(crs_logged_in: Page) -> None:
    """A note under the minimum length stays on Documentation required."""
    AppDocumentationRequired(crs_logged_in).submit_short_note()


@pytest.mark.skip(reason="Fill in AppDocumentationRequired.view_actions from the live desktop screen")
def test_view_actions_lists_documented_actions(crs_logged_in: Page) -> None:
    """View actions lists the actions that must be documented."""
    AppDocumentationRequired(crs_logged_in).view_actions()


@pytest.mark.skip(reason="Fill in AppDocumentationRequired.confirm_note from the live desktop screen")
def test_confirm_note_closes_documentation(crs_logged_in: Page) -> None:
    """A long enough note confirms and leaves Documentation required."""
    AppDocumentationRequired(crs_logged_in).confirm_note("e2e documentation note")

"""Desktop Documentation required screen.

Selectors below are parking spots. Update them from the live desktop screen,
then replace each ``NotImplementedError`` with the flow for that action.
"""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page

from automation.app_pages.base_app.app_base_page import AppBasePage


class AppDocumentationRequired(AppBasePage):
    """Audit note prompted before a Compliance Ready action."""

    def __init__(self, page: Page) -> None:
        """Bind the Playwright page for the desktop app."""
        super().__init__(page)

    @property
    def heading(self) -> Locator:
        """Screen title. Confirm this copy on the desktop app."""
        return self.page.get_by_text("Documentation required", exact=True)

    @property
    def note_field(self) -> Locator:
        """Note entry. Confirm whether the desktop control is a textarea."""
        return self.page.locator("textarea")

    @property
    def confirm_button(self) -> Locator:
        """Primary action that submits the note."""
        return self.page.get_by_role("button", name="Confirm", exact=True)

    @property
    def view_actions_button(self) -> Locator:
        """Opens the list of actions that must be documented."""
        return self.page.get_by_role("button", name="View actions", exact=True)

    @property
    def back_button(self) -> Locator:
        """Leaves the documentation screen without submitting."""
        return self.page.get_by_role("button", name="Back", exact=True)

    @property
    def empty_note_error(self) -> Locator:
        """Error for a blank note. Replace the text once the desktop copy is known."""
        return self.page.get_by_text("Documentation is required", exact=True)

    @property
    def short_note_error(self) -> Locator:
        """Error for a note under the minimum length. Replace once the copy is known."""
        return self.page.get_by_text(re.compile(r"at least", re.IGNORECASE))

    def submit_empty_note(self) -> None:
        """Submit a blank note and require ``empty_note_error``."""
        raise NotImplementedError("Fill in from the live desktop Documentation required screen.")

    def submit_short_note(self) -> None:
        """Submit a too-short note and require ``short_note_error``."""
        raise NotImplementedError("Fill in from the live desktop Documentation required screen.")

    def view_actions(self) -> None:
        """Open View actions and require the documented-action list."""
        raise NotImplementedError("Fill in from the live desktop Documentation required screen.")

    def confirm_note(self, note: str) -> None:
        """Submit ``note`` and require the documentation screen to close."""
        raise NotImplementedError(
            "Fill in from the live desktop Documentation required screen. "
            f"Planned note: {note!r}."
        )

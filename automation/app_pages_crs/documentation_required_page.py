"""Desktop Documentation required screen."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

from automation.app_helpers.locator_helpers import exact_text
from automation.app_pages.base_app.app_base_page import AppBasePage


class AppDocumentationRequired(AppBasePage):
    """Audit note prompted before a Compliance Ready action."""

    HEADING = "Documentation required"
    ACTION_LIST = "Action list"
    MIN_NOTE_LENGTH = 10

    def __init__(self, page: Page) -> None:
        """Bind the Playwright page for the desktop app."""
        super().__init__(page)

    @property
    def dialog(self) -> Locator:
        """Documentation required modal (not the login / set-password Confirm underneath)."""
        return self.page.get_by_role("dialog").filter(
            has=self.page.get_by_text(exact_text(self.HEADING))
        )

    @property
    def heading(self) -> Locator:
        """Screen title."""
        return self.dialog.get_by_text(exact_text(self.HEADING))

    @property
    def action_list_heading(self) -> Locator:
        """Desktop Action list section title (list is inline, not behind View actions)."""
        return self.dialog.get_by_text(exact_text(self.ACTION_LIST))

    @property
    def note_field(self) -> Locator:
        """Note entry labeled for the signed-in user."""
        return self.dialog.get_by_role(
            "textbox",
            name=re.compile(r"Note for robot audit log by", re.IGNORECASE),
        )

    @property
    def confirm_button(self) -> Locator:
        """Primary action that submits the note inside Documentation required."""
        return self.dialog.get_by_role("button", name=exact_text("Confirm"))

    @property
    def view_actions_button(self) -> Locator:
        """Opens the list of actions that must be documented (ODD; not used on desktop)."""
        return self.dialog.get_by_role("button", name=exact_text("View actions"))

    @property
    def back_button(self) -> Locator:
        """Leaves the documentation screen without submitting."""
        return self.dialog.get_by_role("button", name=exact_text("Cancel action"))

    @property
    def empty_note_error(self) -> Locator:
        """Error for a blank note."""
        return self.page.get_by_text(exact_text("Documentation is required"))

    @property
    def short_note_error(self) -> Locator:
        """Error for a note under the minimum length."""
        return self.page.get_by_text(re.compile(r"at least", re.IGNORECASE))

    def submit_empty_note(self) -> None:
        """Submit a blank note and require ``empty_note_error``."""
        expect(self.heading).to_be_visible()
        self.note_field.fill("")
        self.confirm_button.click()
        expect(self.empty_note_error).to_be_visible()
        expect(self.heading).to_be_visible()

    def submit_short_note(self) -> None:
        """Submit a too-short note and require ``short_note_error``."""
        expect(self.heading).to_be_visible()
        self.note_field.fill("too short")
        self.confirm_button.click()
        expect(self.short_note_error).to_be_visible()
        expect(self.heading).to_be_visible()

    def view_actions(self) -> None:
        """Require the Action list section (always visible on the desktop modal)."""
        expect(self.heading).to_be_visible()
        expect(self.action_list_heading).to_be_visible()

    def expect_actions_listed(self, *actions: str) -> None:
        """Require each action label in the Documentation required Action list."""
        self.view_actions()
        for action in actions:
            expect(self.dialog.get_by_text(exact_text(action))).to_be_visible()

    def confirm_note(self, note: str) -> None:
        """Submit ``note`` and require the documentation screen to close."""
        if len(note.strip()) < self.MIN_NOTE_LENGTH:
            raise ValueError(
                f"Documentation note must be at least {self.MIN_NOTE_LENGTH} characters; got {note!r}."
            )
        expect(self.heading).to_be_visible()
        expect(self.note_field).to_be_visible()
        self.note_field.fill(note)
        self.confirm_button.click()
        expect(self.heading).to_be_hidden()

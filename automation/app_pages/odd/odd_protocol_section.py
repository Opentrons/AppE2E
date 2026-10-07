"""Flex ODD protocol list actions and protocol-detail tabs."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

from automation.app_pages.odd.odd_shell import OddShell


class ProtocolSection(OddShell):
    """Protocols list and the pin / delete actions on an open protocol."""

    PROTOCOL_DETAIL_URL = re.compile(r"#?/protocols/.+")

    def __init__(self, page: Page) -> None:
        """Bind the Playwright page for the remote ODD window."""
        super().__init__(page)

    def select_protocol_header(self) -> None:
        """Open the Protocols list.

        Protocol details hides the top nav and uses a back chevron instead.
        """
        if re.search(r"#/protocols/?$", self.page.url):
            expect(self.page.get_by_test_id("protocol_card").first).to_be_visible(timeout=15_000)
            return
        if self.protocols_nav.count() > 0 and self.protocols_nav.is_visible():
            self.open_protocols()
            return
        # The details header's first control is the back chevron (icon only).
        self.press(self.page.get_by_role("button").first)
        expect(self.page).to_have_url(self.PROTOCOLS_URL, timeout=15_000)
        expect(self.page.get_by_test_id("protocol_card").first).to_be_visible(timeout=15_000)

    def select_protocol_name(self, protocol_name: str) -> None:
        """Open a protocol card by its full name, including a pinned card."""
        card = self.page.get_by_test_id("protocol_card").filter(has_text=protocol_name)
        pinned = self.page.get_by_test_id(re.compile(r"^(full|half|regular)_pinned_protocol_card$")).filter(
            has_text=protocol_name
        )
        target = card.or_(pinned)
        expect(target.first).to_be_visible(timeout=15_000)
        self.press(target.first)
        self.page.wait_for_url(self.PROTOCOL_DETAIL_URL, timeout=15_000)
        self.expect_start_setup()
        expect(self.page.get_by_text(protocol_name, exact=True)).to_be_visible()

    def expect_start_setup(self) -> None:
        """Assert Start setup is available on the open protocol."""
        expect(self.page.get_by_role("button", name="Start setup")).to_be_visible(timeout=30_000)

    def expect_protocol_absent(self, protocol_name: str) -> None:
        """Assert ``protocol_name`` is gone from the list and the pinned carousel."""
        unpinned = self.page.get_by_test_id("protocol_card").filter(has_text=protocol_name)
        pinned = self.page.get_by_test_id(re.compile(r"^(full|half|regular)_pinned_protocol_card$")).filter(
            has_text=protocol_name
        )
        expect(unpinned).to_have_count(0, timeout=15_000)
        expect(pinned).to_have_count(0, timeout=15_000)

    def pin_protocol(self) -> None:
        """Pin the open protocol.

        If it is already pinned, unpin it first so this click is the pin action.
        """
        pin = self._pin_button()
        unpin = self._unpin_button()
        if unpin.count() > 0 and unpin.is_visible():
            self.unpin_protocol()
        self.press(pin)
        max_pins = self.page.get_by_text("You've hit your max!", exact=True)
        if max_pins.count() > 0 and max_pins.is_visible():
            self.press(self.page.get_by_role("button", name="Close"))
            raise AssertionError("Pin blocked: the maximum number of pinned protocols is already reached")
        expect(unpin).to_be_visible(timeout=10_000)

    def unpin_protocol(self) -> None:
        """Unpin the open protocol."""
        self.press(self._unpin_button())
        expect(self._pin_button()).to_be_visible(timeout=10_000)

    def open_delete_confirmation(self) -> None:
        """Open the delete confirmation and leave it up."""
        self.press(self.page.get_by_role("button", name="Delete protocol"))
        expect(self._delete_dialog()).to_be_visible(timeout=10_000)

    def delete_protocol(self) -> None:
        """Delete the open protocol and return to the Protocols list."""
        self.open_delete_confirmation()
        self.press(self.page.get_by_role("button", name="Delete", exact=True))
        expect(self.page).to_have_url(self.PROTOCOLS_URL, timeout=60_000)
        expect(self._delete_dialog()).to_be_hidden(timeout=10_000)

    def _pin_button(self) -> Locator:
        return self.page.get_by_role("button", name="Pin protocol", exact=True)

    def _unpin_button(self) -> Locator:
        return self.page.get_by_role("button", name="Unpin protocol", exact=True)

    def _delete_dialog(self) -> Locator:
        return self.page.get_by_text("Delete this protocol?", exact=True)


class OddProtocolOptions(OddShell):
    """Detail tabs and the delete-confirmation Cancel button.

    Summary, Parameters, and Hardware require an open protocol.
    Cancel dismisses the delete confirmation opened from that protocol.
    """

    def __init__(self, page: Page) -> None:
        """Bind the Playwright page for the remote ODD window."""
        super().__init__(page)

    def summary(self) -> None:
        """Open the Summary tab."""
        self.press(self.page.get_by_role("button", name="Summary", exact=True))
        expect(self.page.get_by_text("Date Added")).to_be_visible(timeout=10_000)

    def parameters(self) -> None:
        """Open the Parameters tab."""
        self.press(self.page.get_by_role("button", name="Parameters", exact=True))
        empty = self.page.get_by_text("No parameters specified in this protocol")
        table = self.page.get_by_test_id("Parameters_table")
        expect(empty.or_(table)).to_be_visible(timeout=10_000)

    def Hardware(self) -> None:
        """Open the Hardware tab."""
        self.press(self.page.get_by_role("button", name="Hardware", exact=True))
        located = self.page.get_by_text("Location", exact=True)
        empty = self.page.get_by_text("No hardware is specified for this protocol")
        expect(located.or_(empty)).to_be_visible(timeout=10_000)

    def expect_smoke_parameters(self) -> None:
        """Open Parameters and require the Flex Smoke Test runtime parameters."""
        self.parameters()
        expect(self.page.get_by_text("Number of Stackers", exact=True)).to_be_visible(timeout=10_000)

    def deck(self) -> None:
        """Open the Deck tab and require the protocol deck map."""
        self.press(self.page.get_by_role("button", name="Deck", exact=True))
        expect(self.page.get_by_label("protocol deck map")).to_be_visible(timeout=15_000)

    def liquids(self) -> None:
        """Open the Liquids tab and require the smoke-test water liquid."""
        self.press(self.page.get_by_role("button", name="Liquids", exact=True))
        expect(self.page.get_by_text("Water", exact=True)).to_be_visible(timeout=15_000)

    def cancel(self) -> None:
        """Dismiss the delete confirmation and stay on the open protocol."""
        self.press(self.page.get_by_role("button", name="Cancel", exact=True))
        expect(self.page.get_by_text("Delete this protocol?", exact=True)).to_be_hidden(timeout=10_000)
        expect(self.page.get_by_role("button", name="Start setup")).to_be_visible(timeout=10_000)

"""Page object for ODD Protocols list, sorting, details, pin, and delete."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, expect

from automation.app_pages.odd.odd_shell import OddShell


class OddProtocolsPage(OddShell):
    """Protocols dashboard and protocol details on the Flex ODD."""

    PROTOCOL_DETAIL_URL = re.compile(r"#?/protocols/.+")
    PROTOCOL_CARD_TEST_ID = "protocol_card"
    DETAIL_TABS = ("Summary", "Parameters", "Hardware", "Labware", "Liquids", "Deck")
    SORT_LABELS = ("Protocol Name", "Last Run", "Date Added")

    @property
    def nav_link(self) -> Locator:
        """Top-nav Protocols link."""
        return self.protocols_nav

    @property
    def protocol_cards(self) -> Locator:
        """Unpinned protocol cards on the Protocols dashboard."""
        return self.page.get_by_test_id(self.PROTOCOL_CARD_TEST_ID)

    def open(self) -> None:
        """Open the Protocols dashboard from the ODD top nav."""
        self.open_protocols()

    def expect_protocol_list(self) -> None:
        """Assert the All Protocols list (sort headers + at least one card) is visible."""
        for label in self.SORT_LABELS:
            expect(self.page.get_by_role("button", name=label)).to_be_visible(timeout=15_000)
        expect(self.protocol_cards.first).to_be_visible(timeout=15_000)
        expect(self.page.get_by_role("button", name="Quick transfer")).to_be_visible()

    def expect_protocols(self, protocol_names: tuple[str, ...]) -> None:
        """Assert exact protocol titles are visible on the ODD Protocols page."""
        for protocol_name in protocol_names:
            expect(self.page.get_by_text(protocol_name, exact=True).first).to_be_visible(timeout=120_000)

    def wait_for_protocol_inventory(self) -> None:
        """Wait until the Protocols page has rendered cards, pins, or the empty state."""
        loaded = self.protocol_cards.first.or_(self.page.get_by_text("Pinned Protocols", exact=True)).or_(
            self.page.get_by_text("No protocols to show!", exact=True)
        )
        expect(loaded.first).to_be_visible(timeout=30_000)

    def missing_protocols(self, protocol_names: tuple[str, ...]) -> tuple[str, ...]:
        """Return protocol titles that are not on the Protocols page."""
        missing: list[str] = []
        for protocol_name in protocol_names:
            if self.page.get_by_text(protocol_name, exact=True).count() == 0:
                missing.append(protocol_name)
        return tuple(missing)

    def exercise_sorting(self) -> None:
        """Click each sort header and keep the protocol list visible (C44420)."""
        for label in self.SORT_LABELS:
            btn = self.page.get_by_role("button", name=label)
            expect(btn).to_be_visible()
            self.press(btn)
            expect(self.protocol_cards.first).to_be_visible(timeout=10_000)
            # Toggle a second time to exercise reverse sort direction.
            self.press(btn)
            expect(self.protocol_cards.first).to_be_visible(timeout=10_000)

    def _is_failed_analysis_card(self, card: Locator) -> bool:
        """Return True when the card shows a Failed analysis chip."""
        return card.get_by_test_id("Chip_error").count() > 0

    def _open_card(self, card: Locator) -> None:
        """Click a protocol card and wait for protocol details."""
        expect(card).to_be_visible()
        card.click()
        self.page.wait_for_url(self.PROTOCOL_DETAIL_URL, timeout=15_000)
        expect(self.page.get_by_role("button", name="Start setup")).to_be_visible(timeout=30_000)

    def open_first_healthy_protocol(self) -> None:
        """Open the first protocol card that is not a failed-analysis entry."""
        count = self.protocol_cards.count()
        if count == 0:
            raise AssertionError("No protocol cards on the Protocols list")
        for index in range(count):
            card = self.protocol_cards.nth(index)
            if self._is_failed_analysis_card(card):
                continue
            self._open_card(card)
            return
        raise AssertionError("No healthy (non-failed-analysis) protocol cards found")

    def open_last_healthy_protocol(self) -> None:
        """Open the bottom-most healthy protocol card on the list."""
        count = self.protocol_cards.count()
        if count == 0:
            raise AssertionError("No protocol cards on the Protocols list")
        for index in range(count - 1, -1, -1):
            card = self.protocol_cards.nth(index)
            if self._is_failed_analysis_card(card):
                continue
            self._open_card(card)
            return
        raise AssertionError("No healthy protocol card found near the bottom of the list")

    def expect_setup_details(self) -> None:
        """Assert Protocol Details setup entry points and walk detail tabs (C44418)."""
        expect(self.page.get_by_role("button", name="Start setup")).to_be_visible(timeout=15_000)
        for tab_name in self.DETAIL_TABS:
            tab = self.page.get_by_role("button", name=tab_name, exact=True)
            if tab.count() == 0:
                # Parameters may be omitted for protocols without RTPs.
                continue
            expect(tab.first).to_be_visible()
            tab.first.click()
            expect(tab.first).to_be_visible()

    def pin_protocol(self) -> bool:
        """Pin the open protocol from protocol details.

        Returns True when the protocol is pinned (or already was). Returns False
        when the max-pins alert blocks the action.
        """
        pin = self.page.get_by_role("button", name="Pin protocol")
        unpin = self.page.get_by_role("button", name="Unpin protocol")
        if unpin.count() > 0 and unpin.is_visible():
            return True
        expect(pin).to_be_visible(timeout=15_000)
        pin.click()
        max_pins = self.page.get_by_text("You've hit your max!", exact=True)
        if max_pins.count() > 0 and max_pins.is_visible():
            self.page.get_by_role("button", name="Close").click()
            return False
        expect(unpin).to_be_visible(timeout=10_000)
        return True

    def expect_pinned_section(self) -> None:
        """Assert the Pinned Protocols carousel is present after a pin."""
        expect(self.page.get_by_text("Pinned Protocols", exact=True)).to_be_visible(timeout=15_000)
        pinned = self.page.get_by_test_id(re.compile(r"^(full|half|regular)_pinned_protocol_card$"))
        expect(pinned.first).to_be_visible(timeout=10_000)

    def expect_protocol_pinned(self, protocol_name: str) -> None:
        """Assert ``protocol_name`` is shown in the Pinned Protocols carousel."""
        self.expect_pinned_section()
        pinned = self.page.get_by_test_id(re.compile(r"^(full|half|regular)_pinned_protocol_card$")).filter(
            has_text=protocol_name
        )
        expect(pinned.first).to_be_visible(timeout=10_000)

    def back_to_protocols(self) -> None:
        """Return to the Protocols list via the top nav."""
        self.open()
        expect(self.protocol_cards.first.or_(self.page.get_by_text("Pinned Protocols"))).to_be_visible(timeout=15_000)

    def delete_open_protocol(self) -> None:
        """Delete the protocol open on Protocol Details and confirm."""
        delete = self.page.get_by_role("button", name="Delete protocol")
        expect(delete).to_be_visible(timeout=15_000)
        delete.scroll_into_view_if_needed()
        delete.click()
        expect(self.page.get_by_text("Delete this protocol?", exact=True)).to_be_visible(timeout=10_000)
        confirm = self.page.get_by_role("button", name="Delete", exact=True)
        expect(confirm).to_be_visible()
        confirm.click()
        expect(self.page).to_have_url(self.PROTOCOLS_URL, timeout=60_000)

"""Protocol-list overflow menu component."""

from __future__ import annotations

from playwright.sync_api import Page

from automation.app_pages.components import OverflowMenu


class ProtocolOverflowMenu(OverflowMenu):
    """Stable protocol actions exposed by the list-row overflow menu."""

    ACTION_IDS = {
        "run": "ProtocolOverflowMenu_run",
        "reanalyze": "ProtocolOverflowMenu_reanalyze",
        "send_to_flex": "ProtocolOverflowMenu_sendToOT3",
        "show_in_folder": "ProtocolOverflowMenu_showInFolder",
        "delete": "ProtocolOverflowMenu_deleteProtocol",
    }

    def __init__(self, page: Page) -> None:
        scope = page.locator("body")
        trigger = page.get_by_test_id("ProtocolOverflowMenu_overflowBtn")
        super().__init__(scope, trigger)

    def choose(self, action: str) -> None:
        try:
            test_id = self.ACTION_IDS[action]
        except KeyError as error:
            raise ValueError(f"Unknown protocol action: {action}") from error
        self.open()
        self.click_item(test_id=test_id)

"""Flex ODD overflow (kebab) menu."""

from __future__ import annotations

from playwright.sync_api import Locator, Page, expect

from automation.app_helpers.locator_helpers import exact_text
from automation.app_pages.odd.odd_shell import OddShell


class OddKebabMenu(OddShell):
    """Overflow menu: home gantry, restart, shutdown, deck configuration, lights.

    Restart and shutdown stop at the confirmation modal. Call ``confirm_restart``
    or ``confirm_shutdown`` only when the test intends to power-cycle the robot.
    """

    def __init__(self, page: Page) -> None:
        """Bind the Playwright page for the remote ODD window."""
        super().__init__(page)

    def open(self) -> None:
        """Open the overflow menu."""
        self.open_kebab()

    def close(self) -> None:
        """Dismiss the menu by clicking the modal overlay."""
        overlay = self.page.get_by_label("BackgroundOverlay_ModalShell")
        expect(overlay).to_be_visible(timeout=5_000)
        overlay.click(position={"x": 8, "y": 8})
        expect(self.page.get_by_role("button", name="Home gantry")).to_be_hidden(timeout=5_000)

    def _item(self, name: str) -> Locator:
        """Menu item button. Accessible name includes the icon label, so match by substring."""
        return self.page.get_by_role("button", name=name)

    def home_gantry(self, *, timeout: float = 60_000) -> None:
        """Home the gantry and wait until the menu closes.

        If the door is open the menu still closes and a snackbar asks to close the door.
        """
        self.open()
        item = self._item("Home gantry")
        item.click()
        expect(item).to_be_hidden(timeout=timeout)

    def open_restart(self) -> None:
        """Open the Restart now? confirmation. Does not restart the robot."""
        self.open()
        self._item("Restart robot").click()
        expect(self.page.get_by_test_id("restart_robot_confirmation_description")).to_be_visible(timeout=10_000)

    def cancel_restart(self) -> None:
        """Leave the restart confirmation without restarting."""
        self.page.get_by_role("button", name=exact_text("Go back")).click()
        expect(self.page.get_by_test_id("restart_robot_confirmation_description")).to_be_hidden(timeout=10_000)

    def confirm_restart(self) -> None:
        """Confirm restart. The robot drops offline until it boots again."""
        self.page.get_by_role("button", name=exact_text("Restart")).click()

    def open_shutdown(self) -> None:
        """Open the Turn off robot confirmation. Does not shut the robot down."""
        self.open()
        self._item("Turn off robot").click()
        expect(self.page.get_by_test_id("turn_off_robot_confirmation_description")).to_be_visible(timeout=10_000)

    def cancel_shutdown(self) -> None:
        """Leave the shutdown confirmation without powering off."""
        self.page.get_by_role("button", name=exact_text("Go back")).click()
        expect(self.page.get_by_role("button", name=exact_text("Shutdown"))).to_be_hidden(timeout=10_000)

    def confirm_shutdown(self) -> None:
        """Confirm shutdown. The robot powers off and stays off until someone turns it on."""
        self.page.get_by_role("button", name=exact_text("Shutdown")).click()

    def open_deck_configuration(self) -> None:
        """Open Deck configuration from the overflow menu."""
        self.open()
        self._item("Deck configuration").click()
        expect(self.page).to_have_url(self.DECK_CONFIGURATION_URL, timeout=15_000)
        expect(self.page.get_by_text(exact_text("Deck configuration"))).to_be_visible(timeout=15_000)

    def toggle_lights(self) -> str:
        """Click Lights on / Lights off and return the label now shown.

        The label is the action, so "Lights on" means the lights are currently off.
        The menu stays open after the toggle.
        """
        self.open()
        turn_on = self._item("Lights on")
        turn_off = self._item("Lights off")
        if turn_on.count() > 0 and turn_on.is_visible():
            turn_on.click()
            expect(turn_off).to_be_visible(timeout=10_000)
            return "Lights off"
        expect(turn_off).to_be_visible()
        turn_off.click()
        expect(turn_on).to_be_visible(timeout=10_000)
        return "Lights on"

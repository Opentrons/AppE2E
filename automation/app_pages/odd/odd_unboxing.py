"""Flex ODD screens that appear after Clear all stored data."""

from __future__ import annotations

import re
import time

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from automation.app_helpers.locator_helpers import exact_text
from automation.app_pages.odd.odd_shell import OddShell

# The touchscreen can drop off the network for at least five minutes while Wi-Fi comes up.
_WIFI_CONTINUE_SECONDS = 8 * 60
_ENGLISH_US = "English (US)"
_WIFI_FAILED = re.compile(r"incorrect password|failed to connect", re.IGNORECASE)


def _session_dropped(error: PlaywrightError) -> bool:
    """True when CDP died because the robot left the network."""
    message = str(error).lower()
    return "closed" in message or "disconnected" in message or "connection closed" in message


class OddUnboxingPage(OddShell):
    """Language, welcome, and Wi-Fi setup after an on-device display reset.

    A cleared touchscreen config boots to Choose Language, then Welcome
    (``Get started``), then the network type screen. Welcome is the only
    action on that screen.
    """

    def __init__(self, page: Page) -> None:
        """Bind the Playwright page for the remote ODD window."""
        super().__init__(page)

    def wait_for_setup_screen(self) -> None:
        """Wait out the boot spinner until language or welcome is showing."""
        language = self.page.get_by_text(exact_text("Choose your language"))
        welcome = self.page.get_by_text(exact_text("Welcome to your Opentrons Flex!"))
        expect(language.or_(welcome).first).to_be_visible(timeout=120_000)

    def dismiss_blocking_toasts(self) -> None:
        """Close info toasts that sit over the setup buttons.

        This covers "New module detected. Set up the module for use." and a
        server-version update toast when that toast offers Close.
        """
        for _ in range(3):
            close = self.page.locator('[data-testid^="Toast_"]').get_by_role("button", name=exact_text("Close"))
            if close.count() == 0 or not close.first.is_visible():
                return
            self.press(close.first)
            expect(close.first).to_be_hidden(timeout=10_000)

    def _showing_language(self) -> bool:
        heading = self.page.get_by_text(exact_text("Choose your language"))
        return heading.count() > 0 and heading.is_visible()

    def _showing_welcome(self) -> bool:
        heading = self.page.get_by_text(exact_text("Welcome to your Opentrons Flex!"))
        return heading.count() > 0 and heading.is_visible()

    def select_english_us(self) -> None:
        """Select the English (US) radio. The input is hidden, so activate it directly."""
        radio = self.page.locator(f'input[type="radio"][id="{_ENGLISH_US}"]')
        expect(radio).to_have_count(1, timeout=15_000)
        radio.evaluate("element => element.click()")
        expect(radio).to_be_checked()

    def continue_from_language(self) -> None:
        """Leave Choose Language. The next screen is Welcome."""
        self.press(self.page.get_by_role("button", name=exact_text("Continue")))
        expect(self.page.get_by_text(exact_text("Welcome to your Opentrons Flex!"))).to_be_visible(timeout=15_000)

    def get_started(self) -> None:
        """Click through Welcome. The next screen asks for a network type."""
        self.press(self.page.get_by_role("button", name=exact_text("Get started")))
        expect(self.page.get_by_text(exact_text("Choose network type"))).to_be_visible(timeout=15_000)

    def pass_opening_screens(self) -> None:
        """Welcome and English (US), in whichever order the touchscreen shows them.

        Current software opens Choose Language first, then Welcome. Click Welcome
        first only when that screen is already up.
        """
        self.dismiss_blocking_toasts()
        if self._showing_welcome() and not self._showing_language():
            self.get_started()
            self.dismiss_blocking_toasts()
            if not self._showing_language():
                return
        self.select_english_us()
        self.dismiss_blocking_toasts()
        self.continue_from_language()
        self.dismiss_blocking_toasts()
        self.get_started()

    def choose_wifi(self) -> None:
        """Open the Wi-Fi list from the network type screen."""
        wifi = self.page.get_by_role("button", name=re.compile(r"Wi-Fi"))
        expect(wifi.first).to_be_visible(timeout=15_000)
        self.press(wifi.first)
        expect(self.page.get_by_text(exact_text("Select a network"))).to_be_visible(timeout=15_000)

    def select_network(self, ssid: str) -> None:
        """Wait until ``ssid`` is in the scanned list and select it."""
        row = self.page.get_by_role("button", name=exact_text(ssid))
        expect(row).to_be_visible(timeout=90_000)
        self.press(row)
        expect(self.page.get_by_text(exact_text("Select a security type"))).to_be_visible(timeout=15_000)

    def continue_from_security(self) -> None:
        """Leave the security screen. WPA2 Personal is already selected."""
        self.press(self.page.get_by_role("button", name=exact_text("Continue")))
        expect(self.page.get_by_text(exact_text("Sign into Wi-Fi"))).to_be_visible(timeout=15_000)

    def enter_password_and_connect(self, password: str) -> None:
        """Fill the password field and press Connect.

        The on-screen keyboard is showing, but the field accepts a direct fill.
        """
        field = self.page.get_by_label("wifi_password")
        expect(field).to_be_visible(timeout=15_000)
        field.fill(password)
        expect(field).to_have_value(password)
        self.press(self.page.get_by_role("button", name=exact_text("Connect")))

    def expect_connecting(self, ssid: str) -> None:
        """Assert the touchscreen is connecting to ``ssid``."""
        expect(self.page.get_by_text(exact_text(f"Connecting to {ssid}..."))).to_be_visible(timeout=30_000)

    def _fail_if_wifi_error(self) -> None:
        failed = self.page.get_by_text(_WIFI_FAILED)
        if failed.count() > 0 and failed.first.is_visible():
            raise AssertionError(f"Wi-Fi connect failed: {failed.first.inner_text().strip()}")

    def _reattach(self, robot_ip: str, timeout_s: float) -> None:
        """Attach again after CDP drops during the Wi-Fi handoff."""
        import open_app

        deadline = time.monotonic() + timeout_s
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                _playwright, _browser, page = open_app.connect_odd_playwright(host=robot_ip)
            except (TimeoutError, OSError) as error:
                last_error = error
                # No page to wait on while the robot is off the network.
                time.sleep(2)
                continue
            self.page = page
            return
        raise TimeoutError(f"ODD CDP did not return at {robot_ip}") from last_error

    def continue_when_connected(self, robot_ip: str) -> None:
        """Click Continue on the success screen.

        That button can take at least five minutes while the robot reconnects.
        If CDP drops, attach again and keep waiting.
        """
        deadline = time.monotonic() + _WIFI_CONTINUE_SECONDS
        while time.monotonic() < deadline:
            remaining_ms = int((deadline - time.monotonic()) * 1000)
            try:
                self._fail_if_wifi_error()
                button = self.page.get_by_role("button", name=exact_text("Continue"))
                expect(button).to_be_visible(timeout=min(15_000, remaining_ms))
                self.dismiss_blocking_toasts()
                self.press(button)
                return
            except PlaywrightTimeoutError:
                continue
            except PlaywrightError as error:
                if not _session_dropped(error):
                    raise
                self._reattach(robot_ip, max(1.0, deadline - time.monotonic()))
        raise AssertionError(
            "Continue did not appear after Wi-Fi connect. "
            "The touchscreen can take at least 5 minutes to finish reconnecting."
        )

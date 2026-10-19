"""Flex ODD Instruments dashboard."""

from __future__ import annotations

import re
from typing import Literal

from playwright.sync_api import Locator, Page, expect

from automation.app_helpers.locator_helpers import exact_text
from automation.app_pages.odd.odd_drop_tip_wizard import OddDropTipWizard
from automation.app_pages.odd.odd_shell import OddShell

Mount = Literal["left", "right", "extension"]
PipetteMount = Literal["left", "right", "left+right"]
InfoLabel = Literal["last calibrated", "firmware version", "serial number"]

# Homing to the front of the deck, then the probe sweep itself.
_GANTRY_TIMEOUT_MS = 120_000
_CALIBRATION_TIMEOUT_MS = 600_000

# 96-channel is the "Left + Right Mounts" row, but the route is still /instruments/left.
_PIPETTE_ROW: dict[PipetteMount, re.Pattern[str]] = {
    "left": re.compile(r"^Left Mount"),
    "right": re.compile(r"^Right Mount"),
    "left+right": re.compile(r"^Left \+ Right Mounts"),
}
_PIPETTE_ROUTE: dict[PipetteMount, str] = {
    "left": "left",
    "right": "right",
    "left+right": "left",
}

# Accessible names start with the mount label, then "Empty" or the instrument name.
# "Right Mount" is a substring of "Left + Right Mounts", so left/right stay anchored.
_MOUNT_NAME: dict[Mount, re.Pattern[str]] = {
    "left": re.compile(r"^(Left Mount|Left \+ Right Mounts)"),
    "right": re.compile(r"^Right Mount"),
    "extension": re.compile(r"^Extension Mount"),
}


class OddInstrumentsPage(OddShell):
    """Instruments list and mount detail on the Flex ODD."""

    def __init__(self, page: Page) -> None:
        """Bind the Playwright page for the remote ODD window."""
        super().__init__(page)

    def open(self) -> None:
        """Open the Instruments dashboard from the top nav."""
        self.open_instruments()

    def mount_button(self, mount: Mount) -> Locator:
        """Mount row. A 96-channel pipette is the Left + Right row, addressed as ``left``."""
        return self.page.get_by_role("button", name=_MOUNT_NAME[mount])

    def expect_mounts(self) -> None:
        """Assert the instruments list shows the left (or 96-channel) and gripper rows."""
        expect(self.mount_button("left")).to_be_visible(timeout=15_000)
        expect(self.mount_button("extension")).to_be_visible(timeout=15_000)

    def open_mount(self, mount: Mount) -> None:
        """Open a mount's detail screen."""
        button = self.mount_button(mount)
        self.press(button)
        expect(self.page).to_have_url(re.compile(rf"#?/instruments/{mount}"), timeout=15_000)

    def back(self) -> None:
        """Return from mount detail to the Instruments dashboard.

        The header button's accessible name is the instrument (for example
        "Flex 96-Channel 1000 µL"). The back chevron marks that control.
        """
        back = self.page.get_by_role("button").filter(has=self.page.locator('[aria-roledescription="back"]'))
        expect(back).to_be_visible(timeout=15_000)
        back.click()
        expect(self.page).to_have_url(self.INSTRUMENTS_URL, timeout=15_000)

    def pipette_mount_button(self, mount: PipetteMount) -> Locator:
        """Pipette row. ``left+right`` is the 96-channel "Left + Right Mounts" row."""
        return self.page.get_by_role("button", name=_PIPETTE_ROW[mount])

    def open_pipette(self, mount: PipetteMount) -> None:
        """Open Instruments and the pipette detail for ``left``, ``right``, or ``left+right``."""
        self.open()
        button = self.pipette_mount_button(mount)
        expect(button).to_be_visible(timeout=15_000)
        button.click()
        expect(self.page).to_have_url(
            re.compile(rf"#?/instruments/{_PIPETTE_ROUTE[mount]}"),
            timeout=15_000,
        )

    def calibrate_mount(self) -> None:
        """Start calibration from the open mount screen.

        An uncalibrated pipette shows Calibrate. A calibrated pipette hides that
        button and offers Recalibrate in the overflow menu.
        """
        calibrate = self.page.get_by_role("button", name=re.compile(r"^Calibrate$"))
        if calibrate.count() > 0 and calibrate.first.is_visible():
            calibrate.first.click()
        else:
            self.open_mount_overflow()
            recalibrate = self.page.get_by_role("button", name=re.compile(r"recalibrate", re.I))
            expect(recalibrate.first).to_be_visible(timeout=15_000)
            recalibrate.first.click()
        expect(self.page.get_by_role("button", name="Move gantry to front")).to_be_visible(timeout=15_000)

    def mount_overflow_button(self) -> Locator:
        """Overflow on the open pipette detail.

        The button is labeled "overflow menu button". The icon path inside it
        is ``aria-roledescription="overflow-btn-touchscreen"``. Grippers do not
        render this control.
        """
        return self.page.get_by_role("button", name="overflow menu button").filter(
            has=self.page.locator('[aria-roledescription="overflow-btn-touchscreen"]')
        )

    def open_mount_overflow(self) -> None:
        """Open the pipette overflow and wait until Drop tips is visible.

        A calibrated pipette also shows Recalibrate. Home gantry is not in this
        menu; that control is the top-nav kebab.
        """
        button = self.mount_overflow_button()
        self.press(button)
        expect(self.page.get_by_role("button", name="Drop tips")).to_be_visible(timeout=10_000)

    def drop_tips(self) -> None:
        """Start Drop tips from the open pipette and stop on the first wizard screen.

        The gantry does not move until a later step in that wizard.
        """
        self.open_mount_overflow()
        self.press(self.page.get_by_role("button", name="Drop tips"))
        prompt = self.page.get_by_text("Before you begin, do you need to preserve aspirated liquid?")
        heading = self.page.get_by_text(exact_text("Documentation required"))
        expect(heading.or_(prompt).first).to_be_visible(timeout=20_000)
        OddDropTipWizard(self.page).confirm_audit_note_if_needed()
        expect(prompt).to_be_visible(timeout=30_000)

    def drop_tips_in_waste_chute(self) -> None:
        """Blow out into the waste chute, drop the tip there, and exit the wizard.

        The pipette detail screen must already be open, unless the Drop tips
        wizard is already on screen. The gantry moves during blowout, tip drop,
        and the home that follows Exit.
        """
        self._start_drop_tip_wizard().blow_out_and_drop_in_waste_chute()

    def drop_tips_without_blowout(self) -> None:
        """Skip blowout, drop the tip in the waste chute, and exit.

        Uses "No, proceed to tip removal" on the first wizard screen.
        """
        self._start_drop_tip_wizard().drop_in_waste_chute_without_blowout()

    def _start_drop_tip_wizard(self) -> OddDropTipWizard:
        """Open Drop tips, or continue one that is already on screen."""
        wizard = OddDropTipWizard(self.page)
        prompt = self.page.get_by_text("Before you begin, do you need to preserve aspirated liquid?")
        heading = self.page.get_by_text(exact_text("Documentation required"))
        getting_ready = self.page.get_by_text(re.compile(r"^Getting ready"))
        already_open = prompt.or_(heading).or_(getting_ready)
        if already_open.count() > 0 and already_open.first.is_visible():
            wizard.confirm_audit_note_if_needed()
            expect(prompt).to_be_visible(timeout=30_000)
        else:
            self.drop_tips()
        return wizard

    def move_gantry_to_front(self) -> None:
        """Move the gantry to the front and wait for the attach-probe step."""
        move_gantry = self.page.get_by_role("button", name="Move gantry to front")
        expect(move_gantry).to_be_visible(timeout=15_000)
        move_gantry.click()
        expect(self.page.get_by_role("button", name="Begin calibration")).to_be_visible(timeout=_GANTRY_TIMEOUT_MS)

    def begin_calibration(self) -> None:
        """Begin calibration. The calibration probe must already be on the pipette."""
        print("You must have a calibration probe attached to the mount to initiate this step")
        begin_calibration = self.page.get_by_role("button", name="Begin calibration")
        expect(begin_calibration).to_be_visible(timeout=15_000)
        begin_calibration.click()

    def wait_for_calibration(self) -> None:
        """Wait out probing, confirm the probe-removal step, then exit the wizard."""
        expect(self.page.get_by_text("Stand back")).to_be_visible(timeout=15_000)
        print("calibration in progress")
        expect(self.page.get_by_text("Remove calibration probe")).to_be_visible(timeout=_CALIBRATION_TIMEOUT_MS)
        close = self.page.get_by_role("button", name="Close")
        complete_calibration = self.page.get_by_role("button", name="Complete calibration")
        expect(close.or_(complete_calibration).first).to_be_visible(timeout=15_000)
        if close.is_visible():
            close.click()
        else:
            complete_calibration.click()
        expect(self.page.get_by_text("successfully calibrated")).to_be_visible(timeout=15_000)
        # Header Exit is aria-label="Exit". The blue results button is the other Exit.
        exit_button = self.page.locator("button:not([aria-label='Exit'])").get_by_text(exact_text("Exit"))
        expect(exit_button).to_be_visible(timeout=15_000)
        exit_button.click()
        expect(self.info_item("last calibrated")).to_be_visible(timeout=15_000)

    def calibrate_pipette(self, mount: PipetteMount) -> None:
        """Calibrate one pipette end to end.

        ``mount`` is ``left``, ``right``, or ``left+right`` (96-channel).
        Opens that mount, then runs Calibrate → Move gantry to front →
        Begin calibration → wait for the probe sweep to finish.
        """
        self.open_pipette(mount)
        self.calibrate_mount()
        self.move_gantry_to_front()
        self.begin_calibration()
        self.wait_for_calibration()

    def info_item(self, label: InfoLabel) -> Locator:
        """Detail row on the open mount screen. ``label`` and ``value`` are attributes."""
        return self.page.locator(f'div[label="{label}"]')

    def info_value(self, label: InfoLabel) -> str:
        """Read the ``value`` attribute of a mount detail row."""
        item = self.info_item(label)
        expect(item).to_be_visible(timeout=15_000)
        value = item.get_attribute("value")
        if value is None:
            raise AssertionError(f"Instrument info '{label}' has no value")
        self.readings.instrument[label] = value
        return value

    def last_calibrated(self) -> str:
        """Last calibrated timestamp on the open mount, for example ``9/30/26 20:14 UTC``."""
        return self.info_value("last calibrated")

    def firmware_version(self) -> str:
        """Firmware version on the open mount."""
        return self.info_value("firmware version")

    def serial_number(self) -> str:
        """Serial number on the open mount."""
        return self.info_value("serial number")

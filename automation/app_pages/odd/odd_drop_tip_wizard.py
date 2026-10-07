"""Flex ODD Drop tips wizard: blow out, then drop the tip, then exit.

The setup wizard (not error recovery) routes like this:

1. Before you begin — "Yes, choose blowout location", then Continue.
2. Where to blow out — waste chute, then Continue. A waste chute skips jog
   controls and moves the gantry straight into the blowout.
3. Blowout complete — Continue, which starts the drop-tip route.
4. Where to drop tips — the same waste chute, then Continue.
5. Tip drop complete — the footer Exit (the header Exit is a different control).
   Closing homes the gantry before the pipette detail screen returns.
"""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

from automation.app_pages.odd.odd_shell import OddShell

# Move to the chute, blow out or drop, then home on exit.
_MOTION_TIMEOUT_MS = 120_000

_WASTE_CHUTE = re.compile(r"^Waste chute\b")
_WIZARD_ERROR = re.compile(
    r"Robot door is open|Can't safely drop tips|Error dropping tips|could not be completed|Error moving to position"
)


class OddDropTipWizard(OddShell):
    """Blow out into the waste chute, drop the tip there, and exit.

    Call this after ``OddInstrumentsPage.drop_tips`` has opened the wizard on
    "Before you begin, do you need to preserve aspirated liquid?".
    """

    def __init__(self, page: Page) -> None:
        """Bind the Playwright page for the remote ODD window."""
        super().__init__(page)

    def blow_out_and_drop_in_waste_chute(self) -> None:
        """Run blowout, tip drop in the waste chute, and Exit."""
        self.choose_blowout()
        self.blow_out_in_waste_chute()
        self.continue_to_tip_drop()
        self.drop_tip_in_waste_chute()
        self.exit()

    def drop_in_waste_chute_without_blowout(self) -> None:
        """Skip blowout, drop the tip in the waste chute, and Exit.

        The first screen's other choice is "No, proceed to tip removal".
        That opens the drop-tip location list directly.
        """
        self.skip_blowout()
        self.drop_tip_in_waste_chute()
        self.exit()

    def skip_blowout(self) -> None:
        """Choose "No, proceed to tip removal", then Continue."""
        expect(self.page.get_by_text("Before you begin, do you need to preserve aspirated liquid?")).to_be_visible()
        self.press(self.page.get_by_role("button", name="No, proceed to tip removal"))
        self._continue()
        expect(self.page.get_by_text("Where do you want to drop the attached tips?")).to_be_visible(timeout=15_000)

    def choose_blowout(self) -> None:
        """Choose blowout, then Continue to the location list."""
        expect(self.page.get_by_text("Before you begin, do you need to preserve aspirated liquid?")).to_be_visible()
        self.press(self.page.get_by_role("button", name="Yes, choose blowout location"))
        self._continue()
        expect(self.page.get_by_text("Where do you want to blow out the aspirated liquid?")).to_be_visible(
            timeout=15_000
        )

    def blow_out_in_waste_chute(self) -> None:
        """Blow out into the waste chute and wait for Blowout complete."""
        self._select_waste_chute()
        self._continue()
        self._expect_text_or_error("Blowout complete")

    def continue_to_tip_drop(self) -> None:
        """Leave Blowout complete and open the tip-drop location list."""
        self._continue()
        expect(self.page.get_by_text("Where do you want to drop the attached tips?")).to_be_visible(timeout=15_000)

    def drop_tip_in_waste_chute(self) -> None:
        """Drop the tip in the waste chute and wait for Tip drop complete."""
        self._select_waste_chute()
        self._continue()
        self._expect_text_or_error("Tip drop complete")

    def exit(self) -> None:
        """Press the results Exit and wait until the wizard has closed.

        The header control is ``aria-label="Exit"``. The blue button on
        Tip drop complete is the other Exit, and that is the one that ends
        the wizard. The gantry homes before the overlay goes away.
        """
        footer_exit = self.page.get_by_role("button", name="Exit", exact=True).and_(
            self.page.locator("button:not([aria-label='Exit'])")
        )
        expect(footer_exit).to_be_visible(timeout=15_000)
        self.press(footer_exit)
        pending = self.page.get_by_text(
            re.compile(
                r"Tip drop complete|Stand back, robot is in motion|"
                r"Stand back, robot is dropping tips|Getting ready|"
                r"Robot door is open|Can't safely drop tips|Error dropping tips"
            )
        )
        expect(pending).to_have_count(0, timeout=_MOTION_TIMEOUT_MS)

    def confirm_audit_note_if_needed(self) -> None:
        """Fill the Compliance Ready audit note when one is on screen.

        Creating the maintenance run waits on this screen, so the wizard stays
        on "Getting ready…" until Confirm. Robots without access control skip it.
        """
        heading = self.page.get_by_text("Documentation required", exact=True)
        if heading.count() == 0 or not heading.first.is_visible():
            return
        note = self.page.locator("textarea")
        expect(note.first).to_be_visible(timeout=15_000)
        note.first.fill("e2e drop tip in waste chute")
        self.press(self.page.get_by_role("button", name="Confirm"))
        expect(heading).to_be_hidden(timeout=15_000)

    def _continue(self) -> None:
        """Press the wizard footer Continue. It stays disabled until a choice is made."""
        button = self.page.get_by_role("button", name="Continue")
        expect(button).to_be_enabled(timeout=15_000)
        self.press(button)

    def _select_waste_chute(self) -> None:
        """Select the waste-chute radio.

        The label is "Waste chute in {slot}". The first addressable area is
        often ``1ChannelWasteChute``; a deck whose copy uses the cutout
        (for example "Waste chute in D3") matches the same prefix.
        A pointer click does not toggle this radio on the touchscreen, so the
        input is checked and a bubbling click is sent for React's onChange.
        """
        option = self._waste_chute_label()
        option.evaluate(
            """(node) => {
                const label = node.closest("label");
                const input = label && label.htmlFor ? document.getElementById(label.htmlFor) : null;
                if (!(input instanceof HTMLInputElement)) {
                    throw new Error("Waste chute option has no radio input");
                }
                const tracker = input._valueTracker;
                if (tracker) {
                    tracker.setValue("false");
                }
                input.checked = true;
                input.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
            }"""
        )
        expect(option).to_have_attribute("aria-selected", "true", timeout=15_000)

    def _waste_chute_label(self) -> Locator:
        """The waste-chute ``<label>``. Its text starts with "Waste chute"."""
        label = self.page.locator("label").filter(has_text=_WASTE_CHUTE).first
        try:
            expect(label).to_be_visible(timeout=15_000)
        except AssertionError:
            raise AssertionError(
                "No waste chute in the drop-tip location list. "
                "That option is only shown when a waste chute is configured on the deck."
            ) from None
        return label

    def _expect_text_or_error(self, text: str, *, _docs_attempts: int = 0) -> None:
        """Wait for a success screen, and fail immediately if the wizard shows an error."""
        success = self.page.get_by_text(text, exact=True)
        error = self.page.get_by_text(_WIZARD_ERROR)
        docs = self.page.get_by_text("Documentation required", exact=True)
        expect(success.or_(error).or_(docs).first).to_be_visible(timeout=_MOTION_TIMEOUT_MS)
        if docs.count() > 0 and docs.first.is_visible():
            if _docs_attempts >= 3:
                raise AssertionError("Audit note did not dismiss")
            self.confirm_audit_note_if_needed()
            self._expect_text_or_error(text, _docs_attempts=_docs_attempts + 1)
            return
        if error.count() > 0 and error.first.is_visible():
            raise AssertionError(f"Drop tip wizard failed: {error.first.inner_text()}")
        expect(success).to_be_visible()

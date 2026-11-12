"""Desktop Sign protocol run modal (CRS require-signoff-for-protocol-log).

After a current run becomes terminal, ``useCloseCurrentRun`` opens this modal
before dismiss. The operator must click to sign (legal name) and Submit.
"""

from __future__ import annotations

from playwright.sync_api import Locator, Page, expect

from automation.app_helpers.crs_accounts import CrsAccount, load_crs_account
from automation.app_helpers.locator_helpers import exact_text
from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages.base_app.app_base_page import AppBasePage
from automation.app_pages_crs.compliance_login_page import ComplianceLoginPage
from automation.app_pages_crs.write_documentation import WriteDocumentation


class SignRunPage(AppBasePage):
    """Complete the Sign protocol run modal when Compliance Ready requires it."""

    TITLE = "Sign protocol run"
    CLICK_TO_SIGN = "Click to sign"
    LEGAL_NAME = "Legal name"
    SUBMIT = "Submit"

    def __init__(self, page: Page) -> None:
        """Bind the Playwright page."""
        super().__init__(page)

    @property
    def title(self) -> Locator:
        """Modal title."""
        return self.page.get_by_text(exact_text(self.TITLE))

    @property
    def signature_button(self) -> Locator:
        """Signature field (aria-label Legal name; shows Click to sign until clicked)."""
        return self.page.get_by_role("button", name=exact_text(self.LEGAL_NAME))

    @property
    def submit_button(self) -> Locator:
        """Submit the signed protocol run."""
        return self.page.get_by_role("button", name=exact_text(self.SUBMIT))

    def is_visible(self, *, timeout_ms: int = 1_000) -> bool:
        """True when the Sign protocol run title is showing."""
        try:
            expect(self.title.first).to_be_visible(timeout=timeout_ms)
        except AssertionError:
            return False
        return True

    def complete_if_required(
        self,
        account: CrsAccount | None = None,
        *,
        timeout_ms: int = 30_000,
    ) -> bool:
        """Sign and submit when the modal appears; no-op when it does not.

        Returns True when a signature was submitted.
        """
        if not self.is_visible(timeout_ms=timeout_ms):
            return False

        signer = account or load_crs_account()
        log_step(f"Sign protocol run as {signer.username!r}")
        self._ensure_logged_in_for_sign(signer)
        self._apply_signature()
        self.submit_button.click()
        WriteDocumentation(self.page).complete_if_visible(timeout_ms=5_000)
        expect(self.title.first).to_be_hidden(timeout=60_000)
        log_done("Protocol run signed")
        return True

    def _ensure_logged_in_for_sign(self, account: CrsAccount) -> None:
        """Fill Compliance Ready login when Sign run prompts for credentials."""
        login = ComplianceLoginPage.from_account(self.page, account)
        try:
            expect(login.login_title).to_be_visible(timeout=3_000)
        except AssertionError:
            return
        log_step(f"Log in to sign as {account.username!r}")
        login.username_input.fill(account.username)
        login.password_input.fill(account.password)
        login.submit_button.click()
        WriteDocumentation(self.page).complete_if_visible(timeout_ms=3_000)
        expect(login.login_title).to_be_hidden(timeout=30_000)

    def _apply_signature(self) -> None:
        """Click the signature field so Submit is allowed."""
        signature = self.signature_button
        expect(signature).to_be_visible(timeout=30_000)
        if signature.get_by_text(exact_text(self.CLICK_TO_SIGN)).count() > 0:
            signature.click()
        expect(signature.get_by_text(exact_text(self.CLICK_TO_SIGN))).to_have_count(0)
        expect(self.submit_button).to_be_enabled(timeout=15_000)

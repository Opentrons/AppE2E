"""Page object for the protocol run header actions."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

from automation.app_helpers.page_helpers import require_helper
from automation.app_helpers.screenshot_helper import ScreenshotHelper
from automation.app_pages.base_app.app_base_page import AppBasePage
from automation.app_pages.components import RoundTabBar, StatusChip


class ProtocolRunPage(AppBasePage):
    """Inspect the protocol run shell and operate its run header."""

    ANALYZING_ON_ROBOT = "Analyzing on robot"
    START_RUN = "Start run"
    PAUSE_RUN = "Pause run"
    GO_BACK = "Go back"
    PROCEED_TO_RUN = "Proceed to run"
    PROCEED_TO_RUN_MODAL = "Are you sure you want to proceed to run?"
    MODAL_SHELL = "ModalShell_ModalArea"
    DEFAULT_ANALYSIS_TIMEOUT_MS = 360_000
    PROTOCOL_RUN_URL = re.compile(r"protocol-runs/([^/]+)")
    TABS = (
        ("Setup", "setup"),
        ("Parameters", "runtime-parameters"),
        ("Module Controls", "module-controls"),
        ("Run Preview", "run-preview"),
        ("Camera", "camera"),
    )

    def __init__(
        self,
        page: Page,
        *,
        robot_name: str | None = None,
        run_id: str | None = None,
        shots: ScreenshotHelper | None = None,
    ) -> None:
        """Bind the Playwright page."""
        super().__init__(page)
        self.robot_name = robot_name
        self.run_id = run_id
        self.shots = shots

    def wait_until_open(self, *, timeout_ms: int = 60_000) -> None:
        """Wait until the browser is on a protocol-run details URL."""
        self.page.wait_for_url(self.PROTOCOL_RUN_URL, timeout=timeout_ms)
        if self.run_id is None:
            match = self.PROTOCOL_RUN_URL.search(self.page.url)
            if match is not None:
                self.run_id = match.group(1)

    @property
    def tabs(self) -> RoundTabBar:
        run_id = self.run_id
        if run_id is None:
            match = self.PROTOCOL_RUN_URL.search(self.page.url)
            if match is not None:
                run_id = match.group(1)
                self.run_id = run_id
        if run_id is not None:
            base_url = f"protocol-runs/{run_id}"
        else:
            base_url = "protocol-runs"
        return RoundTabBar(self.page, base_url)

    def open_tab(self, label: str, slug: str) -> None:
        """Open one of the five run-page tabs."""
        self.tabs.open(label, slug)

    def capture_all_tabs(self) -> None:
        """Click each present protocol-run tab and screenshot it."""
        shots = require_helper(self.shots, "ScreenshotHelper", owner="ProtocolRunPage", method="capture_all_tabs")
        self.wait_until_open()
        for label, slug in self.TABS:
            tab = self.tabs.tab(label, slug)
            if tab.count() == 0:
                continue
            self.open_tab(label, slug)
            shots.capture("protocol_run", slug.replace("-", "_"))

    def read_status(self) -> tuple[str, str]:
        """Return the run header status chip variant and text."""
        return StatusChip(self.page).read()

    def read_run_time(self) -> str:
        """Return the value displayed beside the Run Time label."""
        label = self.page.get_by_text("Run Time", exact=True)
        expect(label).to_be_visible()
        value = label.locator("xpath=following::*[self::p or self::span][1]")
        return value.inner_text().strip()

    def analyzing_button(self) -> Locator:
        """Run header button while protocol analysis is in progress."""
        return self.page.get_by_role("button", name=self.ANALYZING_ON_ROBOT)

    def start_run_button(self) -> Locator:
        """Run header Start run (only one exists before the missing-steps modal)."""
        return self.page.get_by_role("button", name=self.START_RUN)

    def pause_run_button(self) -> Locator:
        """Run header Pause run button (visible once the run is active)."""
        return self.page.get_by_role("button", name=self.PAUSE_RUN)

    def missing_steps_modal(self) -> Locator:
        """ConfirmMissingStepsModal via ModalShell aria-label + title text."""
        return (
            self.page.get_by_label(self.MODAL_SHELL)
            .filter(has_text=self.PROCEED_TO_RUN_MODAL)
            .filter(has=self.page.get_by_role("button", name=self.GO_BACK))
        )

    def missing_steps_start_run_button(self) -> Locator:
        """Modal Start run (scoped to ModalShell, next to Go back)."""
        return self.missing_steps_modal().get_by_role("button", name=self.START_RUN)

    def wait_until_analysis_complete(
        self,
        *,
        timeout_ms: int = DEFAULT_ANALYSIS_TIMEOUT_MS,
    ) -> None:
        """Wait until analysis finishes and Start run is available."""
        analyzing = self.analyzing_button()
        if analyzing.count() > 0:
            expect(analyzing.first).to_be_hidden(timeout=timeout_ms)
        expect(self.start_run_button()).to_be_visible(timeout=timeout_ms)

    def confirm_post_start_run_modals(self) -> None:
        """Confirm missing-steps / heater-shaker modals until the run is active."""
        missing_steps = self.missing_steps_modal()
        hs_proceed = self.page.get_by_role("button", name=self.PROCEED_TO_RUN)
        pause = self.pause_run_button()

        expect(missing_steps.or_(hs_proceed).or_(pause)).to_be_visible(timeout=30_000)

        if missing_steps.count() > 0 and missing_steps.is_visible():
            confirm = self.missing_steps_start_run_button()
            expect(confirm).to_be_visible()
            confirm.click()
            expect(missing_steps).to_be_hidden(timeout=15_000)
            expect(hs_proceed.or_(pause)).to_be_visible(timeout=30_000)

        if hs_proceed.count() > 0 and hs_proceed.is_visible():
            hs_proceed.click()
            expect(hs_proceed).to_be_hidden(timeout=15_000)

    def click_start_run(self) -> None:
        """Click header Start run, confirm any proceed modal, and wait until active."""
        self.dismiss_warning_toast()
        # Header is the only "Start run" until ConfirmMissingStepsModal opens.
        button = self.start_run_button()
        expect(button).to_be_visible(timeout=60_000)
        button.click()
        self.confirm_post_start_run_modals()
        expect(self.pause_run_button()).to_be_visible(timeout=60_000)

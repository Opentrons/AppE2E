"""Page object for Robot Settings > File manager."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Locator, Page, expect

from automation.app_helpers.app_readiness import dismiss_blocking_ui
from automation.app_helpers.download_collisions import (
    DEFAULT_DOWNLOADS_DIR,
    prepare_file_manager_downloads,
)
from automation.app_pages.base_app.app_base_page import AppBasePage
from automation.app_pages.base_app.robot_settings_page import RobotSettingsPage
from automation.app_pages.components import BasicButton, ListAccordion, RowCheckbox, StatusChip


@dataclass(frozen=True)
class RunRecord:
    """Visible summary of one protocol run record."""

    date: str
    protocol: str
    status: str
    file_count: int


@dataclass(frozen=True)
class StorageCapacity:
    """Values from the File capacity StorageBar meter."""

    percent_used: int
    percent_available: int
    value_text: str


class FileSection:
    """Shared selectable File Manager section."""

    def __init__(self, root: Locator) -> None:
        self.root = root

    @property
    def header(self) -> Locator:
        return self.root.locator('[data-sentry-component="FileManagementSectionHeader"]').first

    @property
    def select_all_checkbox(self) -> RowCheckbox:
        column_heading = self.root.get_by_text(re.compile(r"^(File type|Date)$")).first
        return RowCheckbox(column_heading.locator(".."))

    def selection_state(self) -> str:
        return self.select_all_checkbox.state()

    def select_all(self) -> None:
        self.select_all_checkbox.check()

    def download_button(self) -> Locator:
        """Visible Download selected control for this section."""
        by_test_id = BasicButton(self.root, "Download selected").locator
        by_role = self.root.get_by_role("button", name="Download selected")
        return by_test_id.or_(by_role).first

    def download(self) -> None:
        button = self.download_button()
        expect(button).to_be_visible()
        expect(button).to_be_enabled()
        button.scroll_into_view_if_needed()
        button.click()


def _section_by_title(page: Page, title: str) -> Locator:
    """Locate a file-management group by its section header title.

    ``ProtocolRunRecords`` (and similar) render a Fragment, so
    ``data-sentry-component=\"ProtocolRunRecords\"`` never appears in the DOM.
    The section root is the parent of ``FileManagementSectionHeader``.
    """
    header = page.locator('[data-sentry-component="FileManagementSectionHeader"]').filter(
        has=page.get_by_text(title, exact=True)
    )
    expect(header).to_be_visible()
    return header.locator("xpath=..")


class DiagnosticFilesSection(FileSection):
    """Troubleshooting and calibration log selection."""

    TROUBLESHOOTING_LOGS = "Troubleshooting Logs"
    CALIBRATION_LOGS = "Calibration Logs"

    def rows(self) -> list[str]:
        labels = self.root.get_by_text(re.compile(r".+ Logs$"))
        return [label.inner_text().strip() for label in labels.all() if label.is_visible()]

    def select(self, name: str) -> None:
        label = self.root.get_by_text(name, exact=True)
        expect(label).to_have_count(1)
        RowCheckbox(label.locator("..")).check()

    def download_file_type(self, name: str) -> None:
        """Check one File type row and click Download selected."""
        self.select(name)
        self.download()


class ProtocolRunRecordsSection(FileSection):
    """Selectable protocol run records and their file drawers."""

    NO_RECENT_RUNS = "No recent runs"

    @property
    def record_roots(self) -> Locator:
        return self.root.locator('[data-sentry-component="ListAccordion"]')

    def is_empty(self) -> bool:
        empty = self.root.get_by_text(self.NO_RECENT_RUNS, exact=True)
        return empty.count() > 0 and empty.first.is_visible()

    def rows(self) -> list[RunRecord]:
        if self.is_empty():
            return []
        result: list[RunRecord] = []
        for index in range(self.record_roots.count()):
            root = self.record_roots.nth(index)
            values = [text.strip() for text in root.locator("p").all_inner_texts() if text.strip()]
            variant, status = StatusChip(root).read()
            del variant
            date = root.get_by_test_id("Tag_default").inner_text().strip()
            try:
                status_index = values.index(status)
                protocol = values[values.index(date) + 1]
                count = int(values[status_index + 1])
            except (ValueError, IndexError):
                protocol, count = "", 0
            result.append(RunRecord(date=date, protocol=protocol, status=status, file_count=count))
        return result

    def _record(self, key: int | str) -> Locator:
        if isinstance(key, int):
            return self.record_roots.nth(key)
        return self.record_roots.filter(has_text=key).first

    def select(self, key: int | str) -> None:
        RowCheckbox(self._record(key)).check()

    def expand(self, key: int | str) -> None:
        ListAccordion(self._record(key)).expand()

    def files(self, key: int | str) -> dict[str, str]:
        root = self._record(key)
        ListAccordion(root).expand()
        items = root.get_by_test_id("ListItem_defaultOnColor")
        result: dict[str, str] = {}
        for index in range(items.count()):
            values = [text.strip() for text in items.nth(index).locator("p").all_inner_texts()]
            if len(values) >= 2:
                result[values[0]] = values[1]
        return result

    def delete(self) -> None:
        """Assert the destructive action is available without opening its unmodeled modal."""
        expect(BasicButton(self.header, "Delete selected").locator).to_be_visible()


class FileManagerPage(AppBasePage):
    """Read storage and manage downloadable robot files."""

    FILE_CAPACITY_LABEL = "File capacity"
    ROBOT_STORAGE = "Robot Storage"
    DOWNLOAD_IN_PROGRESS = "Downloading diagnostic files"
    DOWNLOAD_SUCCESS = "Files successfully downloaded"
    # Parallel robot log fetches are usually ~15–40s; allow headroom for lab Wi‑Fi.
    # Keep under the suite's 300s per-test timeout.
    DOWNLOAD_TIMEOUT_MS = 240_000

    def __init__(self, page: Page, *, robot_name: str) -> None:
        super().__init__(page)
        self.robot_name = robot_name
        self._downloads_dir = DEFAULT_DOWNLOADS_DIR

    @property
    def file_manager_url(self) -> re.Pattern[str]:
        return re.compile(
            rf"#/devices/{re.escape(self.robot_name)}/robot-settings/file-manager"
        )

    @property
    def root(self) -> Locator:
        return self.page.locator('[data-sentry-component="RobotSettingsFileManager"]')

    def open(self) -> None:
        """Open Robot Settings → File manager, preferring a hash deep-link."""
        dismiss_blocking_ui(self.page)
        if not self.file_manager_url.search(self.page.url):
            base = self.page.url.split("#", 1)[0]
            self.page.goto(f"{base}#/devices/{self.robot_name}/robot-settings/file-manager")
            try:
                expect(self.page).to_have_url(self.file_manager_url, timeout=10_000)
            except AssertionError:
                RobotSettingsPage(self.page, robot_name=self.robot_name).navigate(
                    tab=("File manager", "file-manager")
                )
        expect(self.root).to_be_visible()
        expect(self.page.get_by_text(self.ROBOT_STORAGE, exact=True)).to_be_visible()

    def prepare_downloads(self) -> Path:
        """Clear collision files and route saves to Downloads (no OS Save picker)."""
        self._downloads_dir = prepare_file_manager_downloads(self.page, self.robot_name)
        return self._downloads_dir

    def wait_for_download_started(self, *, timeout: float = 15_000) -> None:
        """Fail fast if Download selected never kicked off the in-progress toast."""
        toast = self.page.get_by_test_id("Toast_info").filter(
            has_text=self.DOWNLOAD_IN_PROGRESS
        )
        expect(toast).to_be_visible(timeout=timeout)

    def wait_for_download_success(self, *, timeout: float | None = None) -> None:
        """Wait for the success toast after Download selected."""
        toast = self.page.get_by_test_id("Toast_success").filter(
            has_text=self.DOWNLOAD_SUCCESS
        )
        expect(toast).to_be_visible(
            timeout=self.DOWNLOAD_TIMEOUT_MS if timeout is None else timeout
        )

    def expect_download_file(self, filename: str, *, timeout: float | None = None) -> Path:
        """Wait until ``filename`` exists and is non-empty under the prepared Downloads dir."""
        path = self._downloads_dir / filename
        deadline_ms = self.DOWNLOAD_TIMEOUT_MS if timeout is None else timeout
        end = time.monotonic() + (deadline_ms / 1000.0)
        while time.monotonic() < end:
            if path.is_file() and path.stat().st_size > 0:
                return path
            self.page.wait_for_timeout(250)
        raise AssertionError(f"Expected downloaded file at {path}")

    def _wait_for_destination_intercept(self, *, timeout: float = 15_000) -> dict:
        """Info toast is painted before IPC; wait until destination injection is observed."""
        self.page.wait_for_function(
            """() => {
              const calls = window.__otSaveDirIntercepts || []
              return calls.some(
                (call) =>
                  typeof call.destination === "string" && call.destination.length > 0
              )
            }""",
            timeout=timeout,
        )
        intercepts = self.page.evaluate("() => window.__otSaveDirIntercepts || []")
        return next(
            call
            for call in reversed(intercepts)
            if call.get("destination")
        )

    def complete_diagnostic_download(
        self,
        diagnostics: DiagnosticFilesSection,
        name: str,
        *,
        expected_file: str | None = None,
    ) -> Path:
        """Select a filetype, click Download, and wait until the file is written.

        Defaults ``expected_file`` to ``{robot}_logs.zip`` for Troubleshooting Logs,
        otherwise ``{robot}-calibration.json``.
        """
        if expected_file is None:
            if name == DiagnosticFilesSection.TROUBLESHOOTING_LOGS:
                expected_file = f"{self.robot_name}_logs.zip"
            else:
                expected_file = f"{self.robot_name}-calibration.json"
        self.prepare_downloads()
        diagnostics.download_file_type(name)
        self.wait_for_download_started()
        self._wait_for_destination_intercept()
        self.wait_for_download_success()
        return self.expect_download_file(expected_file, timeout=5_000)

    def capacity(self) -> StorageCapacity:
        """Read the Robot Storage File capacity meter."""
        meter = self.page.get_by_role("meter", name=self.FILE_CAPACITY_LABEL)
        expect(meter).to_be_visible()
        used = int(meter.get_attribute("aria-valuenow") or "0")
        available = max(0, 100 - used)
        value_text = (meter.get_attribute("aria-valuetext") or "").strip()
        return StorageCapacity(
            percent_used=used,
            percent_available=available,
            value_text=value_text,
        )

    def diagnostics(self) -> DiagnosticFilesSection:
        root = self.page.locator('[data-sentry-component="DiagnosticsFiles"]').filter(
            has=self.page.get_by_text("Diagnostic Files", exact=True)
        )
        if root.count() == 0:
            root = _section_by_title(self.page, "Diagnostic Files")
        return DiagnosticFilesSection(root)

    def run_records(self) -> ProtocolRunRecordsSection:
        return ProtocolRunRecordsSection(_section_by_title(self.page, "Protocol Run Records"))

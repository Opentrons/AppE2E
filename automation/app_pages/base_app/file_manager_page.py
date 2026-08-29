"""Page object for Robot Settings > File manager."""

from __future__ import annotations

import re
from dataclasses import dataclass

from playwright.sync_api import Locator, Page, expect

from automation.app_helpers.download_collisions import clear_file_manager_downloads
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

    def download(self) -> None:
        BasicButton(self.header, "Download selected").click()


def prepare_file_manager_downloads(robot_name: str) -> None:
    """Clear stable Download filenames so Electron won't show a Replace sheet.

    Call before Download selected or Delete selected (delete re-downloads first).
    Native OS conflict dialogs are invisible to Playwright/Stagewright.
    """
    clear_file_manager_downloads(robot_name)


class DiagnosticFilesSection(FileSection):
    """Troubleshooting and calibration log selection."""

    def rows(self) -> list[str]:
        labels = self.root.get_by_text(re.compile(r".+ Logs$"))
        return [label.inner_text().strip() for label in labels.all() if label.is_visible()]

    def select(self, name: str) -> None:
        label = self.root.get_by_text(name, exact=True)
        expect(label).to_have_count(1)
        RowCheckbox(label.locator("..")).check()


class ProtocolRunRecordsSection(FileSection):
    """Selectable protocol run records and their file drawers."""

    @property
    def record_roots(self) -> Locator:
        return self.root.locator('[data-sentry-component="ListAccordion"]')

    def rows(self) -> list[RunRecord]:
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

    def __init__(self, page: Page, *, robot_name: str) -> None:
        super().__init__(page)
        self.robot_name = robot_name

    def open(self) -> None:
        RobotSettingsPage(self.page, robot_name=self.robot_name).navigate(tab=("File manager", "file-manager"))
        expect(self.page.get_by_text("Robot Storage", exact=True)).to_be_visible()

    def prepare_downloads(self) -> None:
        """Remove existing Downloads targets for this robot before save/delete."""
        prepare_file_manager_downloads(self.robot_name)

    def read_capacity(self) -> int:
        meter = self.page.get_by_role("meter", name="File capacity")
        expect(meter).to_be_visible()
        return int(meter.get_attribute("aria-valuenow") or "0")

    def diagnostics(self) -> DiagnosticFilesSection:
        root = self.page.locator('[data-sentry-component="DiagnosticsFiles"]').filter(
            has=self.page.get_by_text("Diagnostic Files", exact=True)
        )
        return DiagnosticFilesSection(root)

    def run_records(self) -> ProtocolRunRecordsSection:
        root = self.page.locator('[data-sentry-component="ProtocolRunRecords"]').filter(
            has=self.page.get_by_text("Protocol Run Records", exact=True)
        )
        return ProtocolRunRecordsSection(root)

"""Language setting on the Flex ODD."""

from __future__ import annotations

from playwright.sync_api import Locator, expect

from automation.app_helpers.locator_helpers import exact_text
from automation.app_pages.odd.odd_readings import ProtocolRunRecord
from automation.app_pages.odd.odd_shell import OddShell


class FileManager_Download(OddShell):
    """File Manager child screen."""

    File_manager = "File manager"
    Download = "Download all"

    def click_file_manager(self):
        self.page.get_by_text(self.File_manager).click()
        self.page.get_by_text(self.Download).click()
        self.back_button.click()


class FileManagerProtocolRunRecord(OddShell):
    """Protocol Run Records tab on File Manager.

    Each row is a protocol name, a last-run timestamp, and a status chip.
    An empty robot shows "No run records found" instead of the table.
    """

    FILE_MANAGER = "File manager"
    PROTOCOL_RUN_RECORDS = "Protocol Run Records"
    NO_RUN_RECORDS = "No run records found"
    _HEADERS = ("Protocol name", "Last run date", "Run status")

    def _print_table(self, records: list[ProtocolRunRecord]) -> None:
        """Print protocol name, last run date, and run status as a text table."""
        body = [(record.protocol_name, record.last_run_date, record.run_status) for record in records]
        widths = [len(header) for header in self._HEADERS]
        for row in body:
            for index, cell in enumerate(row):
                widths[index] = max(widths[index], len(cell))

        def format_row(cells: tuple[str, ...]) -> str:
            return "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(cells))

        print(format_row(self._HEADERS))
        print("  ".join("-" * width for width in widths))
        for row in body:
            print(format_row(row))

    def _record_from_row(self, row: Locator) -> ProtocolRunRecord:
        """Read the three paragraphs on one run-record row: name, date, status."""
        texts = [text.strip() for text in row.locator("p").all_inner_texts() if text.strip()]
        if len(texts) < 3:
            raise LookupError(f"Protocol run record row is missing cells: {texts!r}")
        return ProtocolRunRecord(protocol_name=texts[0], last_run_date=texts[1], run_status=texts[2])

    def read_protocol_run_records(self) -> list[ProtocolRunRecord]:
        """Read the open Protocol Run Records table and print it.

        Returns an empty list and prints a notice when the robot has no run
        records. The rows are also stored on ``self.readings.protocol_run_records``.
        """
        root = self.page.locator('[data-sentry-component="ProtocolRunRecords"]')
        empty = self.page.get_by_text(exact_text(self.NO_RUN_RECORDS))
        expect(root.or_(empty).first).to_be_visible(timeout=15_000)
        rows = root.locator('[data-testid^="ListItem_"]')
        try:
            if empty.is_visible() or rows.count() == 0:
                raise LookupError("No protocol run records")
            records = [self._record_from_row(rows.nth(index)) for index in range(rows.count())]
        except LookupError as exc:
            if str(exc) != "No protocol run records":
                raise
            print(exc)
            self.readings.protocol_run_records = []
            return []
        self._print_table(records)
        self.readings.protocol_run_records = records
        return records

    def click_protocol_run_record(self) -> list[ProtocolRunRecord]:
        """Open File Manager → Protocol Run Records, print the table, and go back."""
        tab = self.page.get_by_text(exact_text(self.PROTOCOL_RUN_RECORDS))
        if tab.count() == 0 or not tab.first.is_visible():
            row = self.page.get_by_text(exact_text(self.FILE_MANAGER))
            if row.count() == 0 or not row.first.is_visible():
                self.open_settings()
            expect(row.first).to_be_visible(timeout=15_000)
            row.first.click()
            tab = self.page.get_by_text(exact_text(self.PROTOCOL_RUN_RECORDS))
        expect(tab.first).to_be_visible(timeout=15_000)
        tab.first.click()
        records = self.read_protocol_run_records()
        self.back_button.click()
        return records


class NetworkSettings(OddShell):
    """Network settings child screen and the connection details modal.

    Each details row is a label paragraph beside a value paragraph, for example
    "IP Address" beside "10.14.19.167".
    """

    NETWORK_SETTINGS = "Network settings"
    CONNECTED = "Connected"
    VIEW_DETAILS = "View details"
    IP_ADDRESS = "IP Address"
    SECURITY_TYPE = "Security Type"
    SUBNET_MASK = "Subnet Mask"
    MAC_ADDRESS = "MAC Address"

    def detail_value(self, label: str) -> str:
        """Return the text shown beside a details-modal label."""
        name = self.page.get_by_text(exact_text(label))
        expect(name).to_be_visible(timeout=15_000)
        value = name.locator("..").locator("p").last
        expect(value).to_be_visible()
        return value.inner_text().strip()

    def read_connection_details(self) -> dict[str, str]:
        """Read IP, security, subnet, and MAC from the open details modal."""
        details = {
            self.IP_ADDRESS: self.detail_value(self.IP_ADDRESS),
            self.SECURITY_TYPE: self.detail_value(self.SECURITY_TYPE),
            self.SUBNET_MASK: self.detail_value(self.SUBNET_MASK),
            self.MAC_ADDRESS: self.detail_value(self.MAC_ADDRESS),
        }
        self.readings.network = details
        return details

    def click_network_settings(self) -> dict[str, str]:
        """Open the connected network and return the values beside each details label.

        Child screens hide the top nav, so Settings is opened only when the
        Network settings row is not already on screen. View details is clicked
        directly when the Wi-Fi screen is already showing.
        """
        view_details = self.page.get_by_text(exact_text(self.VIEW_DETAILS))
        if view_details.count() == 0 or not view_details.first.is_visible():
            network_settings = self.page.get_by_text(exact_text(self.NETWORK_SETTINGS))
            if network_settings.count() == 0 or not network_settings.first.is_visible():
                self.open_settings()
            expect(network_settings.first).to_be_visible(timeout=15_000)
            network_settings.first.click()
            self.page.get_by_text(exact_text(self.CONNECTED)).first.click()
            view_details = self.page.get_by_text(exact_text(self.VIEW_DETAILS))
        expect(view_details.first).to_be_visible(timeout=15_000)
        view_details.first.click()
        details = self.read_connection_details()
        self.page.get_by_label("closeIcon").click()
        self.back_button.click()
        return details


class RobotSystemVersion(OddShell):
    """Robot system version child screen.

    The version string is the paragraph beside the "Current Version" label,
    for example "10.1.0-alpha.1".
    """

    ROBOT_SYSTEM_VERSION = "Robot system version"
    CURRENT_VERSION = "Current Version"

    def current_version(self) -> str:
        """Return the text shown beside the Current Version label."""
        label = self.page.get_by_text(exact_text(self.CURRENT_VERSION))
        expect(label).to_be_visible(timeout=15_000)
        value = label.locator("..").locator("p").last
        expect(value).to_be_visible()
        version = value.inner_text().strip()
        self.readings.robot_system_version = version
        return version

    def click_robot_system_version(self) -> str:
        """Open Robot system version and return the current version string."""
        row = self.page.get_by_role("button", name=self.ROBOT_SYSTEM_VERSION)
        if row.count() == 0 or not row.first.is_visible():
            self.open_settings()
        expect(row.first).to_be_visible(timeout=15_000)
        row.first.click()
        version = self.current_version()
        self.back_button.click()
        return version


class LanguageToggle(OddShell):
    """Language child screen: English (US) and 中文.

    Option labels stay in their own language. The screen header is "Language"
    in English and "语言 (Language)" after 中文 is selected. ``click_language``
    switches to 中文, confirms that header, then restores English (US).
    """

    ENGLISH = "English (US)"
    CHINESE = "中文"
    HEADER_EN = "Language"
    HEADER_ZH = "语言 (Language)"

    def language_row(self) -> Locator:
        """Settings row. The accessible name includes the current language."""
        return self.page.get_by_role("button", name=self.HEADER_EN)

    def _option(self, label: str) -> Locator:
        """A language choice. These are labels, and the names are not translated."""
        return self.page.get_by_text(exact_text(label))

    def _header(self, name: str) -> Locator:
        """Language screen title."""
        return self.page.get_by_role("heading", name=exact_text(name))

    def click_language(self) -> None:
        """Open Language from Robot Settings, switch to 中文, then restore English (US)."""
        self.open_settings()
        row = self.language_row()
        expect(row).to_be_visible(timeout=15_000)
        expect(row).to_contain_text(self.ENGLISH)
        row.scroll_into_view_if_needed()
        row.click()

        english = self._option(self.ENGLISH)
        chinese = self._option(self.CHINESE)
        expect(self.back_button).to_be_visible(timeout=15_000)
        expect(self._header(self.HEADER_EN)).to_be_visible()
        expect(english).to_be_visible()
        expect(chinese).to_be_visible()

        chinese.click()
        expect(self._header(self.HEADER_ZH)).to_be_visible(timeout=15_000)

        english.click()
        expect(self._header(self.HEADER_EN)).to_be_visible(timeout=15_000)

        self.back_button.click()
        expect(row).to_be_visible(timeout=15_000)
        expect(row).to_contain_text(self.ENGLISH)

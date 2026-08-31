"""Page object for a robot's Run History tab."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from automation.app_pages.base_app.app_base_page import AppBasePage
from automation.app_pages.base_app.devices_page import DevicesPage
from automation.app_pages.components import BasicButton


class RunHistoryPage(AppBasePage):
    """Inspect and download the robot's run history."""

    def __init__(self, page: Page, *, robot_name: str) -> None:
        super().__init__(page)
        self.robot_name = robot_name

    def open(self) -> None:
        devices = DevicesPage(self.page, robot_name=self.robot_name)
        devices.open_run_history(use_tabs=True)
        expect(self.page).to_have_url(devices.robot_run_history_url)

    def download_all(self) -> None:
        BasicButton(self.page, "Download all").click()

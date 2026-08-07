"""Page object for Robot Settings > Calibration workflows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from playwright.sync_api import Locator, Page, expect

from automation.app_helpers.app_readiness import click_visible_overlays
from automation.app_pages.base_app.app_base_page import AppBasePage
from automation.app_pages.base_app.robot_settings_page import RobotSettingsPage

CalibrationCategory = Literal["pipette", "gripper", "module"]

# Pipette probing typically takes ~5 minutes; allow headroom before failing.
PIPETTE_CALIBRATION_MOTION_TIMEOUT_MS = 600_000
# Module probe calibration is shorter than pipette offset, but still allow headroom.
MODULE_CALIBRATION_MOTION_TIMEOUT_MS = 300_000
MODULE_FIRMWARE_UPDATE_TIMEOUT_MS = 120_000
WIZARD_STEP_TIMEOUT_MS = 120_000


@dataclass(frozen=True)
class CalibrationItem:
    """One row from pipette, gripper, or module calibration tables."""

    category: CalibrationCategory
    label: str
    serial: str
    status: str
    row_index: int

    @property
    def is_calibrated(self) -> bool:
        return self.status not in (
            CalibrationHelper.NOT_CALIBRATED,
            CalibrationHelper.NO_CALIBRATION_REQUIRED,
        )

    @property
    def state_label(self) -> str:
        if self.status == CalibrationHelper.NOT_CALIBRATED:
            return "not calibrated"
        if self.status == CalibrationHelper.NO_CALIBRATION_REQUIRED:
            return "no calibration required"
        return "calibrated"


class CalibrationHelper(AppBasePage):
    """Robot Settings calibration tab — list status and start specific workflows.

    Prefer the high-level entry points from tests::

        calibration.list_calibration_status()
        calibration.verify_overflow_menus(categories=["gripper"])
        calibration.start_calibration("pipette")
        calibration.start_calibration("gripper")
        calibration.start_calibration("module", index=0)
        calibration.run_96_channel_calibration()
        calibration.run_heater_shaker_calibration()
        calibration.run_temperature_module_calibration()
        calibration.run_thermocycler_calibration()
    """

    ABOUT_CALIBRATION = "About Calibration"
    PIPETTE_CALIBRATIONS = "Pipette Calibrations"
    GRIPPER_CALIBRATION = "Gripper Calibration"
    MODULE_CALIBRATION = "Module Calibration"
    NOT_CALIBRATED = "Not calibrated"
    NO_CALIBRATION_REQUIRED = "No calibration required"
    DOWNLOAD_LOGS = "Download calibration logs"

    PIPETTE_OVERFLOW = "CalibrationOverflowMenu_button_pipetteOffset"
    GRIPPER_OVERFLOW = "CalibrationOverflowMenu_button_gripperCalibration"
    MODULE_OVERFLOW = "ModuleCalibrationOverflowMenu"
    CALIBRATE_PIPETTE = "CalibrationOverflowMenu_button_calibrate"
    MOVE_GANTRY_TO_FRONT = "Move gantry to front"
    BEGIN_CALIBRATION = "Begin calibration"
    COMPLETE_CALIBRATION = "Complete calibration"
    RESULTS_EXIT = "Results_exit"
    WIZARD_HEADER_EXIT = "Exit"
    SUCCESS_ICON_ALT = "Success Icon"
    # Module wizard (Heater-Shaker / Temp / TC) — ModuleWizardFlows copy.
    HEATER_SHAKER_LABEL = "Heater-Shaker"
    TEMPERATURE_MODULE_LABEL = "Temperature"
    THERMOCYCLER_LABEL = "Thermocycler"
    START_SETUP = "Start setup"
    CONFIRM_LOCATION = "Confirm location"
    CONFIRM_PLACEMENT = "Confirm placement"
    INSTALL_UPDATE = "Install update"
    MODULE_SETUP_FINISH = "Finish"
    # Copy varies by wizard step: PlaceAdapter uses shared "robot is in motion",
    # AttachProbe uses module_wizard_flows "calibration in progress".
    IN_MOTION_RE = re.compile(
        r"stand back,.*(?:robot is in motion|calibration in progress|is calibrating)",
        re.IGNORECASE,
    )
    CALIBRATING_RE = re.compile(r"is calibrating", re.IGNORECASE)
    # Flows with existing calibration data say "successfully recalibrated".
    SUCCESS_RE = re.compile(r"successfully\s+(?:re)?calibrated", re.IGNORECASE)
    # Module setup success: "{{module}} successfully set up"
    MODULE_SETUP_SUCCESS_RE = re.compile(r"successfully set up", re.IGNORECASE)

    def __init__(self, page: Page, *, robot_name: str) -> None:
        super().__init__(page)
        self.robot_name = robot_name
        self.last_success_message: str | None = None
        self._robot_settings = RobotSettingsPage(page, robot_name=robot_name)

    def navigate(self) -> None:
        """Open Robot Settings and switch to the Calibration tab."""
        self._robot_settings.navigate()
        self._robot_settings.open_tab("Calibration", "calibration")
        self.expect_loaded()

    def get_calibration_page(self) -> None:
        """Alias for :meth:`navigate` — kept for existing tests."""
        self.navigate()

    def expect_loaded(self) -> None:
        """Wait for the main calibration sections and instrument data to render."""
        expect(self.page.get_by_text(self.ABOUT_CALIBRATION, exact=True)).to_be_visible()
        expect(self.page.get_by_text(self.PIPETTE_CALIBRATIONS, exact=True)).to_be_visible()
        expect(self.page.get_by_text(self.GRIPPER_CALIBRATION, exact=True)).to_be_visible()
        expect(self.page.get_by_text(self.MODULE_CALIBRATION, exact=True)).to_be_visible()
        self.wait_for_calibration_data()

    def wait_for_calibration_data(self) -> None:
        """Wait until calibration tables or overflow controls are populated."""
        loaded = (
            self.pipette_overflow_button()
            .or_(self.gripper_overflow_button())
            .or_(self.module_overflow_buttons().first)
            .or_(self.page.get_by_text(self.NOT_CALIBRATED, exact=True))
            .or_(self.page.get_by_text(self.NO_CALIBRATION_REQUIRED, exact=True))
        )
        try:
            expect(loaded.first).to_be_visible(timeout=30_000)
        except AssertionError as exc:
            if self.page.get_by_text("No pipette attached", exact=True).is_visible():
                raise RuntimeError(
                    "Robot Settings > Calibration shows 'No pipette attached'. "
                    "Ensure QA1Potato is connectable before running calibration tests."
                ) from exc
            raise

    def download_logs_button(self) -> Locator:
        return self.page.get_by_role("button", name=self.DOWNLOAD_LOGS)

    def pipette_overflow_button(self) -> Locator:
        return self.page.get_by_role("button", name=self.PIPETTE_OVERFLOW)

    def gripper_overflow_button(self) -> Locator:
        return self.page.get_by_role("button", name=self.GRIPPER_OVERFLOW)

    def module_overflow_buttons(self) -> Locator:
        return self.page.get_by_role("button", name=self.MODULE_OVERFLOW)

    def _row_from_overflow(self, button: Locator) -> Locator:
        return button.locator("xpath=ancestor::tr[1]")

    def _item_from_row(self, row: Locator, *, category: CalibrationCategory, row_index: int) -> CalibrationItem:
        cells = row.locator("td")
        if category == "pipette":
            model = cells.nth(0).locator("p").first.inner_text().strip()
            serial = cells.nth(0).locator("p").nth(1).inner_text().strip()
            label = model
        elif category == "gripper":
            serial = cells.nth(0).inner_text().strip()
            label = "Gripper"
        else:
            label = cells.nth(0).inner_text().strip()
            serial = cells.nth(1).inner_text().strip()
        status = self._status_from_row(row)
        return CalibrationItem(category=category, label=label, serial=serial, status=status, row_index=row_index)

    def _status_from_row(self, row: Locator) -> str:
        """Read Last Calibrated cell text, including nested ``Not calibrated`` spans."""
        if row.get_by_text(self.NOT_CALIBRATED, exact=True).count() > 0:
            return self.NOT_CALIBRATED
        if row.get_by_text(self.NO_CALIBRATION_REQUIRED, exact=True).count() > 0:
            return self.NO_CALIBRATION_REQUIRED
        cells = row.locator("td")
        return cells.nth(cells.count() - 2).inner_text().strip()

    def get_pipette_calibration_items(self) -> list[CalibrationItem]:
        items: list[CalibrationItem] = []
        buttons = self.pipette_overflow_button()
        for index in range(buttons.count()):
            row = self._row_from_overflow(buttons.nth(index))
            items.append(self._item_from_row(row, category="pipette", row_index=index))
        return items

    def get_gripper_calibration_items(self) -> list[CalibrationItem]:
        items: list[CalibrationItem] = []
        buttons = self.gripper_overflow_button()
        for index in range(buttons.count()):
            row = self._row_from_overflow(buttons.nth(index))
            items.append(self._item_from_row(row, category="gripper", row_index=index))
        return items

    def get_module_calibration_items(self) -> list[CalibrationItem]:
        items: list[CalibrationItem] = []
        buttons = self.module_overflow_buttons()
        for index in range(buttons.count()):
            row = self._row_from_overflow(buttons.nth(index))
            items.append(self._item_from_row(row, category="module", row_index=index))
        return items

    def get_all_calibration_items(self) -> list[CalibrationItem]:
        return (
            self.get_pipette_calibration_items()
            + self.get_gripper_calibration_items()
            + self.get_module_calibration_items()
        )

    def get_uncalibrated_items(self, *, categories: list[CalibrationCategory] | None = None) -> list[CalibrationItem]:
        return [
            item for item in self.get_calibration_items(categories=categories) if item.status == self.NOT_CALIBRATED
        ]

    def get_calibration_items(self, *, categories: list[CalibrationCategory] | None = None) -> list[CalibrationItem]:
        """Return calibration rows, optionally filtered by category."""
        items = self.get_all_calibration_items()
        if categories is None:
            return items
        wanted = set(categories)
        return [item for item in items if item.category in wanted]

    def list_calibration_status(self, *, categories: list[CalibrationCategory] | None = None) -> list[CalibrationItem]:
        """Return calibration rows (optionally filtered). Raises if none found."""
        items = self.get_calibration_items(categories=categories)
        if not items:
            raise RuntimeError("No calibration rows found on Robot Settings > Calibration")
        return items

    def is_calibration_needed(self, *, categories: list[CalibrationCategory] | None = None) -> bool:
        """Return True when any matching item still shows ``Not calibrated``."""
        items = self.list_calibration_status(categories=categories)
        return any(item.status == self.NOT_CALIBRATED for item in items)

    def check_if_calibration_needed(self) -> bool:
        """Alias for :meth:`is_calibration_needed` — kept for existing tests."""
        return self.is_calibration_needed()

    def find_item(
        self,
        category: CalibrationCategory,
        *,
        serial: str | None = None,
        label_contains: str | None = None,
        index: int = 0,
        uncalibrated_only: bool = False,
    ) -> CalibrationItem:
        """Resolve one calibration row by category and optional filters."""
        items = self.get_calibration_items(categories=[category])
        if uncalibrated_only:
            items = [item for item in items if item.status == self.NOT_CALIBRATED]
        if serial is not None:
            items = [item for item in items if item.serial == serial]
        if label_contains is not None:
            needle = label_contains.lower()
            items = [item for item in items if needle in item.label.lower()]
        if not items:
            filters = []
            if serial is not None:
                filters.append(f"serial={serial!r}")
            if label_contains is not None:
                filters.append(f"label_contains={label_contains!r}")
            if uncalibrated_only:
                filters.append("uncalibrated_only")
            detail = f" ({', '.join(filters)})" if filters else ""
            raise RuntimeError(f"No {category} calibration row found{detail}")
        if index < 0 or index >= len(items):
            raise RuntimeError(f"{category} calibration index {index} out of range (found {len(items)})")
        return items[index]

    def is_96_channel_item(self, item: CalibrationItem) -> bool:
        """True when a pipette row looks like a Flex 96-channel."""
        if item.category != "pipette":
            return False
        if any(marker.lower() in item.label.lower() for marker in ("96", "p1000_96")):
            return True
        row = self._row_from_overflow(self.overflow_button_for_item(item))
        return row.get_by_text("Both", exact=True).count() > 0

    def overflow_button_for_item(self, item: CalibrationItem) -> Locator:
        if item.category == "pipette":
            return self.pipette_overflow_button().nth(item.row_index)
        if item.category == "gripper":
            return self.gripper_overflow_button().nth(item.row_index)
        return self.module_overflow_buttons().nth(item.row_index)

    def expect_overflow_menu_for_item(self, item: CalibrationItem) -> None:
        """Assert the overflow menu shows a calibrate action for ``item``."""
        expect(self._menu_action_for_item(item).first).to_be_visible()

    def _menu_action_for_item(self, item: CalibrationItem) -> Locator:
        if item.category == "pipette":
            return (
                self.page.get_by_role("button", name=self.CALIBRATE_PIPETTE)
                .or_(self.page.get_by_role("button", name="Calibrate pipette"))
                .or_(self.page.get_by_role("button", name="Recalibrate pipette"))
            )
        if item.category == "gripper":
            return (
                self.page.get_by_role("button", name="Calibrate gripper")
                .or_(self.page.get_by_role("button", name="Recalibrate gripper"))
                .or_(self.page.get_by_text("Calibrate gripper", exact=True))
                .or_(self.page.get_by_text("Recalibrate gripper", exact=True))
            )
        return self.page.get_by_role("button", name="Calibrate module").or_(
            self.page.get_by_role("button", name="Recalibrate module")
        )

    def _dismiss_overflow_overlay(self) -> None:
        """Dismiss the transparent overlay from pipette/gripper/module overflow menus."""
        click_visible_overlays(self.page)

    def _any_overflow_menu_open(self) -> bool:
        return (
            self.page.get_by_role("button", name=self.CALIBRATE_PIPETTE).is_visible()
            or self.page.get_by_role("button", name="Calibrate gripper").is_visible()
            or self.page.get_by_role("button", name="Recalibrate gripper").is_visible()
            or self.page.get_by_role("button", name="Calibrate module").is_visible()
            or self.page.get_by_role("button", name="Recalibrate module").is_visible()
        )

    def _overflow_menu_is_open(self, item: CalibrationItem) -> bool:
        return self._menu_action_for_item(item).first.is_visible()

    def close_all_overflow_menus(self) -> None:
        """Close any open calibration overflow menus and their blocking overlays."""
        if (
            not self._any_overflow_menu_open()
            and self.page.locator('[data-sentry-component="Overlay"]:visible').count() == 0
        ):
            return

        self._dismiss_overflow_overlay()

        for _ in range(4):
            if self.page.locator('[data-sentry-component="Overlay"]:visible').count() == 0:
                break
            self._dismiss_overflow_overlay()

        visible_overlays = self.page.locator('[data-sentry-component="Overlay"]:visible')
        if visible_overlays.count() > 0:
            expect(visible_overlays.first).to_have_count(0, timeout=5_000)

    def close_overflow_menu(self, item: CalibrationItem | None = None) -> None:
        """Dismiss an open overflow menu overlay before opening the next one."""
        overlay_visible = self.page.locator('[data-sentry-component="Overlay"]:visible').count()
        if item is not None and self._overflow_menu_is_open(item):
            self._dismiss_overflow_overlay()
            expect(self._menu_action_for_item(item).first).to_be_hidden(timeout=5_000)
        elif overlay_visible > 0 or self._any_overflow_menu_open():
            self.close_all_overflow_menus()

    def open_overflow_menu_for_item(self, item: CalibrationItem) -> None:
        """Open the row overflow menu for a pipette, gripper, or module."""
        self.close_all_overflow_menus()
        btn = self.overflow_button_for_item(item)
        expect(btn).to_be_visible()
        btn.scroll_into_view_if_needed()
        btn.click()
        self.expect_overflow_menu_for_item(item)

    def open_overflow_menus_for_uncalibrated(
        self, *, categories: list[CalibrationCategory] | None = None
    ) -> list[CalibrationItem]:
        """Open and verify overflow menus for every matching ``Not calibrated`` row."""
        return self.verify_overflow_menus(categories=categories, uncalibrated_only=True)

    def verify_overflow_menus(
        self,
        *,
        categories: list[CalibrationCategory] | None = None,
        uncalibrated_only: bool = True,
    ) -> list[CalibrationItem]:
        """Open/close overflow menus for selected calibration rows.

        Use ``categories`` to limit which workflows to exercise, e.g.
        ``categories=["gripper", "module"]``.
        """
        items = (
            self.get_uncalibrated_items(categories=categories)
            if uncalibrated_only
            else self.get_calibration_items(categories=categories)
        )
        for item in items:
            self.open_overflow_menu_for_item(item)
            self.close_overflow_menu(item)
        return items

    def open_pipette_overflow_menu(self) -> None:
        btn = self.pipette_overflow_button()
        expect(btn).to_be_visible()
        btn.click()

    def open_gripper_overflow_menu(self) -> None:
        btn = self.gripper_overflow_button()
        expect(btn).to_be_visible()
        btn.click()

    def open_module_overflow_menu(self, index: int = 0) -> None:
        btn = self.module_overflow_buttons().nth(index)
        expect(btn).to_be_visible()
        btn.click()

    def start_calibration_for_item(self, item: CalibrationItem) -> None:
        """Open the row overflow menu and click Calibrate / Recalibrate."""
        self.open_overflow_menu_for_item(item)
        self._menu_action_for_item(item).first.click()

    def start_calibration(
        self,
        category: CalibrationCategory,
        *,
        index: int = 0,
        serial: str | None = None,
        label_contains: str | None = None,
        uncalibrated_only: bool = False,
    ) -> CalibrationItem:
        """Start a specific calibration workflow from Robot Settings.

        Examples::

            calibration.start_calibration("pipette")
            calibration.start_calibration("gripper")
            calibration.start_calibration("module", index=0)
            calibration.start_calibration("pipette", label_contains="96")
        """
        item = self.find_item(
            category,
            serial=serial,
            label_contains=label_contains,
            index=index,
            uncalibrated_only=uncalibrated_only,
        )
        self.start_calibration_for_item(item)
        return item

    def start_pipette_calibration(self, *, index: int = 0) -> CalibrationItem:
        """Open pipette overflow menu and choose Calibrate pipette."""
        return self.start_calibration("pipette", index=index)

    def start_gripper_calibration(self) -> CalibrationItem:
        """Open gripper overflow menu and choose Calibrate gripper."""
        return self.start_calibration("gripper")

    def start_module_calibration(
        self,
        index: int = 0,
        *,
        label_contains: str | None = None,
    ) -> CalibrationItem:
        """Open a module overflow menu and choose Calibrate module.

        Pass ``label_contains`` to target a specific module type (e.g. ``"Heater-Shaker"``).
        """
        return self.start_calibration("module", index=index, label_contains=label_contains)

    def start_96_channel_calibration(self) -> CalibrationItem:
        """Open overflow and choose Calibrate for an attached Flex 96-channel."""
        pipettes = self.get_calibration_items(categories=["pipette"])
        matches = [item for item in pipettes if self.is_96_channel_item(item)]
        if not matches:
            # Fallback: Flex 96 still uses the pipette overflow control; accept sole pipette.
            if len(pipettes) == 1:
                matches = pipettes
            else:
                raise RuntimeError("No 96-channel pipette calibration row found on Robot Settings > Calibration")
        item = matches[0]
        self.start_calibration_for_item(item)
        return item

    def open_96_channel_calibration(self) -> CalibrationItem:
        """Alias for :meth:`start_96_channel_calibration`."""
        return self.start_96_channel_calibration()

    def click_move_gantry_to_front(self) -> None:
        btn = self.page.get_by_role("button", name=self.MOVE_GANTRY_TO_FRONT)
        expect(btn).to_be_visible(timeout=WIZARD_STEP_TIMEOUT_MS)
        btn.click()

    def click_begin_calibration(self) -> None:
        """Click Begin calibration after the probe-attach step is ready."""
        btn = self.page.get_by_role("button", name=self.BEGIN_CALIBRATION)
        expect(btn).to_be_visible(timeout=WIZARD_STEP_TIMEOUT_MS)
        btn.click()

    def wait_for_pipette_calibration_motion(self, *, timeout_ms: float = PIPETTE_CALIBRATION_MOTION_TIMEOUT_MS) -> None:
        """Wait for the 'is calibrating' screen to appear, then finish (~5+ minutes)."""
        calibrating = self.page.get_by_text(self.CALIBRATING_RE)
        expect(calibrating.first).to_be_visible(timeout=WIZARD_STEP_TIMEOUT_MS)
        expect(calibrating.first).to_be_hidden(timeout=timeout_ms)

    def click_complete_calibration(self) -> None:
        btn = self.page.get_by_role("button", name=self.COMPLETE_CALIBRATION)
        expect(btn).to_be_visible(timeout=WIZARD_STEP_TIMEOUT_MS)
        btn.click()

    def wait_for_pipette_calibration_success(self) -> str:
        """Wait for the success screen and return its header text."""
        expect(self.page.get_by_alt_text(self.SUCCESS_ICON_ALT)).to_be_visible(timeout=WIZARD_STEP_TIMEOUT_MS)
        header = self.page.get_by_text(self.SUCCESS_RE).first
        expect(header).to_be_visible(timeout=WIZARD_STEP_TIMEOUT_MS)
        return header.inner_text().strip()

    def results_exit_button(self) -> Locator:
        """The blue Exit button on the results screen (not the header Exit).

        Its ``aria-label`` overrides the visible ``Exit`` text, so the accessible
        name is ``Results_exit``.
        """
        return self.page.get_by_role("button", name=self.RESULTS_EXIT, exact=True)

    def click_results_exit(self) -> None:
        """Click the blue results Exit and confirm the wizard closed.

        The header also renders an ``Exit`` control, so target the results
        button by its ``Results_exit`` label and fall back to the header only if
        the wizard is still open.
        """
        btn = self.results_exit_button()
        expect(btn).to_be_visible(timeout=WIZARD_STEP_TIMEOUT_MS)
        btn.click()

        success_icon = self.page.get_by_alt_text(self.SUCCESS_ICON_ALT)
        try:
            expect(success_icon).to_be_hidden(timeout=15_000)
        except AssertionError:
            header_exit = self.page.get_by_role("button", name=self.WIZARD_HEADER_EXIT, exact=True)
            if header_exit.count() > 0 and header_exit.first.is_visible():
                header_exit.first.click()
            expect(success_icon).to_be_hidden(timeout=WIZARD_STEP_TIMEOUT_MS)

        self.expect_wizard_closed()

    def expect_wizard_closed(self) -> None:
        """Wait until the wizard is gone and Robot Settings > Calibration is back."""
        expect(self.page.get_by_text(self.ABOUT_CALIBRATION, exact=True)).to_be_visible(timeout=WIZARD_STEP_TIMEOUT_MS)

    def run_96_channel_calibration(
        self, *, calibration_timeout_ms: float = PIPETTE_CALIBRATION_MOTION_TIMEOUT_MS
    ) -> CalibrationItem:
        """Run the full Flex 96-channel pipette calibration wizard end-to-end.

        Flow: overflow → Move gantry to front → Begin calibration (after probe attach) →
        wait for probing to finish → Complete calibration → success → Results Exit.
        """
        item = self.start_96_channel_calibration()
        self.click_move_gantry_to_front()
        self.click_begin_calibration()
        self.wait_for_pipette_calibration_motion(timeout_ms=calibration_timeout_ms)
        self.click_complete_calibration()
        self.last_success_message = self.wait_for_pipette_calibration_success()
        self.click_results_exit()
        return item

    def start_heater_shaker_calibration(self) -> CalibrationItem:
        """Open overflow and choose Calibrate for an attached Heater-Shaker module."""
        return self.start_module_calibration(label_contains=self.HEATER_SHAKER_LABEL)

    def start_temperature_module_calibration(self) -> CalibrationItem:
        """Open overflow and choose Calibrate for an attached Temperature Module."""
        return self.start_module_calibration(label_contains=self.TEMPERATURE_MODULE_LABEL)

    def start_thermocycler_calibration(self) -> CalibrationItem:
        """Open overflow and choose Calibrate for an attached Thermocycler module."""
        return self.start_module_calibration(label_contains=self.THERMOCYCLER_LABEL)

    def wait_past_module_firmware_check(self) -> None:
        """Skip or complete the UpdateFirmware step, then wait for Before Beginning.

        When firmware is current the wizard auto-advances after a brief check.
        When an update is available, click Install update and wait for Start setup.
        """
        start_setup = self.page.get_by_role("button", name=self.START_SETUP)
        install_update = self.page.get_by_role("button", name=self.INSTALL_UPDATE)
        expect(start_setup.or_(install_update)).to_be_visible(timeout=WIZARD_STEP_TIMEOUT_MS)
        if install_update.is_visible():
            install_update.click()
        expect(start_setup).to_be_visible(timeout=MODULE_FIRMWARE_UPDATE_TIMEOUT_MS)

    def click_start_setup(self) -> None:
        btn = self.page.get_by_role("button", name=self.START_SETUP)
        expect(btn).to_be_visible(timeout=WIZARD_STEP_TIMEOUT_MS)
        btn.click()

    def click_confirm_location(self) -> None:
        btn = self.page.get_by_role("button", name=self.CONFIRM_LOCATION)
        expect(btn).to_be_visible(timeout=WIZARD_STEP_TIMEOUT_MS)
        expect(btn).to_be_enabled(timeout=WIZARD_STEP_TIMEOUT_MS)
        btn.click()

    def confirm_placement_button(self) -> Locator:
        return self.page.get_by_role("button", name=self.CONFIRM_PLACEMENT)

    def click_confirm_placement(self) -> None:
        """Confirm calibration-adapter placement once the tile is interactive.

        The button only renders after the module/labware load commands finish, and
        stays disabled until the maintenance run exists.
        """
        btn = self.confirm_placement_button()
        expect(btn).to_be_visible(timeout=WIZARD_STEP_TIMEOUT_MS)
        expect(btn).to_be_enabled(timeout=WIZARD_STEP_TIMEOUT_MS)
        btn.click()

    def in_motion_banner(self) -> Locator:
        """The 'Stand back…' in-progress screen shown between wizard steps."""
        return self.page.get_by_text(self.IN_MOTION_RE)

    def verify_robot_in_motion(
        self,
        *,
        next_step: Locator | None = None,
        appear_timeout_ms: float = 15_000,
        clear_timeout_ms: float = WIZARD_STEP_TIMEOUT_MS,
    ) -> bool:
        """Verify an in-motion screen appears and clears without clicking anything.

        Short motion screens can clear before Playwright polls, so ``next_step``
        lets the check pass when the wizard has already advanced. Returns whether
        the motion screen was actually observed.
        """
        motion = self.in_motion_banner().first
        try:
            expect(motion).to_be_visible(timeout=appear_timeout_ms)
        except AssertionError:
            if next_step is not None and next_step.count() > 0 and next_step.first.is_visible():
                return False
            raise
        expect(motion).to_be_hidden(timeout=clear_timeout_ms)
        return True

    def wait_for_module_calibration_motion(self, *, timeout_ms: float = MODULE_CALIBRATION_MOTION_TIMEOUT_MS) -> None:
        """Wait out probing after Begin calibration, then expect Complete calibration."""
        self.verify_robot_in_motion(
            next_step=self.page.get_by_role("button", name=self.COMPLETE_CALIBRATION),
            clear_timeout_ms=timeout_ms,
        )

    def wait_for_module_setup_success(self) -> str:
        """Wait for the module setup success screen and return its header text."""
        expect(self.page.get_by_alt_text(self.SUCCESS_ICON_ALT)).to_be_visible(timeout=WIZARD_STEP_TIMEOUT_MS)
        header = self.page.get_by_text(self.MODULE_SETUP_SUCCESS_RE).first
        expect(header).to_be_visible(timeout=WIZARD_STEP_TIMEOUT_MS)
        return header.inner_text().strip()

    def click_module_setup_finish(self) -> None:
        """Click Finish on the module setup success screen and return to Calibration."""
        btn = self.page.get_by_role("button", name=self.MODULE_SETUP_FINISH, exact=True)
        expect(btn).to_be_visible(timeout=WIZARD_STEP_TIMEOUT_MS)
        btn.click()
        self.expect_wizard_closed()

    def run_module_calibration(
        self,
        label_contains: str,
        *,
        calibration_timeout_ms: float = MODULE_CALIBRATION_MOTION_TIMEOUT_MS,
    ) -> CalibrationItem:
        """Run ModuleWizardFlows calibration for a module matching ``label_contains``.

        Shared by Heater-Shaker, Temperature Module, and Thermocycler — all use the
        default getModuleSetupSteps path: firmware → before beginning → select
        location → place adapter → attach probe → detach probe → success.

        Flow (from Robot Settings > Calibration): overflow → firmware check →
        Start setup → Confirm location → in motion → Confirm placement →
        in motion → Begin calibration (after probe attach) → probing →
        Complete calibration (after probe removal) → success → Finish.
        """
        item = self.start_module_calibration(label_contains=label_contains)
        self.wait_past_module_firmware_check()
        self.click_start_setup()
        self.click_confirm_location()
        self.verify_robot_in_motion(next_step=self.confirm_placement_button())
        self.click_confirm_placement()
        self.verify_robot_in_motion(next_step=self.page.get_by_role("button", name=self.BEGIN_CALIBRATION))
        self.click_begin_calibration()
        self.wait_for_module_calibration_motion(timeout_ms=calibration_timeout_ms)
        self.click_complete_calibration()
        self.last_success_message = self.wait_for_module_setup_success()
        self.click_module_setup_finish()
        return item

    def run_heater_shaker_calibration(
        self, *, calibration_timeout_ms: float = MODULE_CALIBRATION_MOTION_TIMEOUT_MS
    ) -> CalibrationItem:
        """Run the full Heater-Shaker ModuleWizardFlows calibration end-to-end."""
        return self.run_module_calibration(self.HEATER_SHAKER_LABEL, calibration_timeout_ms=calibration_timeout_ms)

    def run_temperature_module_calibration(
        self, *, calibration_timeout_ms: float = MODULE_CALIBRATION_MOTION_TIMEOUT_MS
    ) -> CalibrationItem:
        """Run the full Temperature Module ModuleWizardFlows calibration end-to-end."""
        return self.run_module_calibration(self.TEMPERATURE_MODULE_LABEL, calibration_timeout_ms=calibration_timeout_ms)

    def run_thermocycler_calibration(
        self, *, calibration_timeout_ms: float = MODULE_CALIBRATION_MOTION_TIMEOUT_MS
    ) -> CalibrationItem:
        """Run the full Thermocycler ModuleWizardFlows calibration end-to-end."""
        return self.run_module_calibration(self.THERMOCYCLER_LABEL, calibration_timeout_ms=calibration_timeout_ms)

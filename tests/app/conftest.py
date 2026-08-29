"""Pytest fixtures for Opentrons Electron regression tests."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from packaging.version import Version
from playwright.sync_api import Browser, Page, Playwright
from pytest_html import extras as html_extras

import bootstrap  # noqa: F401
import open_app
from automation.app_helpers.app_version import has_device_details_tabs, parse_app_version
from automation.app_helpers.dev_robot_setup import ensure_localhost_robot_discovered, wait_for_robot_server
from automation.app_helpers.left_nav import navigate_to
from automation.app_helpers.reporting import (
    capture_failure_screenshot,
    ensure_test_results_dir,
    slugify_nodeid,
    start_test_recording,
    stop_test_recording,
)
from automation.app_helpers.robot_connection import RobotConnection, resolve_robot_ip
from automation.app_helpers.robot_profiles import (
    DEFAULT_HARDWARE_ROBOT_NAME,
    RobotProfile,
    get_robot_profile,
)
from automation.app_helpers.robot_usb import find_opentrons_usb_port
from automation.app_helpers.screenshot_helper import ScreenshotHelper
from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages import AppSettingsPage, DevicesPage
from run_config import is_headed_run

DEFAULT_PROTOCOL_NAME = os.environ.get(
    # Prefix match: finds "Flex Smoke Test - v2.28", "v2.29", etc.
    "PROTOCOL_NAME",
    "Flex Smoke Test",
)
print(f"DEFAULT_PROTOCOL_NAME: {DEFAULT_PROTOCOL_NAME} from os.environ.get('PROTOCOL_NAME')")


def _resolve_robot_name(config: pytest.Config, profile: RobotProfile | None) -> str:
    """Resolve robot display name from profile, CLI flag, or environment."""
    if profile is not None:
        return profile.robot_name
    from_cli = config.getoption("--robot-name")
    if from_cli:
        return from_cli.strip()
    return os.environ.get("ROBOT_NAME", DEFAULT_HARDWARE_ROBOT_NAME).strip()


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register robot name and launch profile CLI options."""
    parser.addoption(
        "--robot-name",
        action="store",
        default=None,
        help="Robot display name on the Devices page (overrides ROBOT_NAME env var).",
    )
    parser.addoption(
        "--robot-profile",
        action="store",
        default=None,
        help=(
            "Launch profile (e.g. fake-robot starts make -C app dev + local robot-server). "
            "Overrides --robot-name when set."
        ),
    )


def _terminate_process(process: subprocess.Popen | None) -> None:
    """Terminate a subprocess, escalating to kill when it does not exit in time."""
    if process is None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except Exception:
        process.kill()


def _connect_robot_for_tests(
    profile: RobotProfile | None,
    *,
    cli_ip: str | None = None,
) -> RobotConnection:
    """Connect to USB, localhost, or Wi-Fi robot and verify ``/health``."""
    if profile is not None and not profile.require_hardware_connection:
        connection = RobotConnection(ip="127.0.0.1")
        connection("/health")
        return connection

    usb_port = find_opentrons_usb_port()
    if usb_port is not None:
        connection = RobotConnection(usb_port=usb_port)
        connection("/health")
        return connection

    ip = resolve_robot_ip(cli_ip=cli_ip)
    connection = RobotConnection(ip=ip)
    connection("/health")
    return connection


@pytest.fixture(scope="session")
def robot_profile(request: pytest.FixtureRequest) -> RobotProfile | None:
    """Return the selected robot launch profile, if any."""
    profile_id = request.config.getoption("--robot-profile")
    if profile_id:
        profile = get_robot_profile(profile_id.strip())
        log_step(f"Robot profile: {profile.profile_id} (robot name: {profile.robot_name})")
        return profile
    return None


@pytest.fixture(scope="session")
def robot_server_process(
    robot_profile: RobotProfile | None,
) -> Generator[subprocess.Popen | None, None, None]:
    """Start ``make -C robot-server dev-flex`` for the fake-robot profile."""
    if robot_profile is None or not robot_profile.start_robot_server:
        yield None
        return

    try:
        wait_for_robot_server(timeout=3.0)
        log_step("Local robot-server already running — reusing")
        yield None
        return
    except TimeoutError:
        pass

    repo_root = open_app.find_monorepo_root()
    log_step("Starting local Flex robot-server (make -C robot-server dev-flex)")
    process = subprocess.Popen(
        ["make", "-C", "robot-server", "dev-flex"],
        cwd=repo_root,
    )
    try:
        wait_for_robot_server()
        log_step("Local robot-server is healthy")
        yield process
    finally:
        _terminate_process(process)


@pytest.fixture(scope="session")
def robot_connection(
    robot_profile: RobotProfile | None,
    robot_server_process: subprocess.Popen | None,
    request: pytest.FixtureRequest,
) -> RobotConnection:
    """Connect to the robot over USB, Wi-Fi, or localhost before the app opens the port."""
    del robot_server_process
    cli_ip = request.config.getoption("--robot-ip")
    return _connect_robot_for_tests(robot_profile, cli_ip=cli_ip)


@pytest.fixture(scope="session")
def run_local_app(
    robot_connection: RobotConnection,
    robot_profile: RobotProfile | None,
    request: pytest.FixtureRequest,
) -> Generator[Page, None, None]:
    """Launch (or attach to) the Opentrons desktop app and yield the Playwright page."""
    del robot_connection

    headed = is_headed_run(request.config)
    use_dev_app = robot_profile is not None and robot_profile.app_mode == "dev"
    if headed:
        log_step("Headed mode: Electron window stays visible; bringing app to front each test")
    if use_dev_app:
        log_step("App mode: dev (make -C app dev)")

    process: subprocess.Popen | None = None
    playwright: Playwright | None = None
    browser: Browser | None = None
    app_log = Path("test-results/app-console.log")

    if open_app.should_attach_only():
        playwright, browser, page = open_app.connect_playwright()
    elif use_dev_app:
        assert robot_profile is not None
        process, playwright, browser, page = open_app.launch_dev_and_connect(
            quiet=True,
            log_file=app_log if headed else None,
            opentrons_project=robot_profile.opentrons_project,
        )
    else:
        process, playwright, browser, page = open_app.launch_and_connect(
            quiet=True,
            log_file=app_log if headed else None,
        )

    open_app.prepare_app_page(page)
    request.session.playwright_debug_page = page
    if robot_profile is not None and robot_profile.add_localhost_manual_ip:
        log_step(f"Ensuring localhost robot '{robot_profile.robot_name}' is discoverable")
        ensure_localhost_robot_discovered(page, robot_name=robot_profile.robot_name)
    if headed:
        page.bring_to_front()
    yield page

    if browser is not None:
        try:
            browser.close()
        except Exception:
            pass
    if playwright is not None:
        playwright.stop()
    _terminate_process(process)


@pytest.fixture(scope="session")
def robot_name(request: pytest.FixtureRequest, robot_profile: RobotProfile | None) -> str:
    """Resolved robot display name used on the Devices page."""
    name = _resolve_robot_name(request.config, robot_profile)
    log_step(f"Robot name: {name}")
    return name


@pytest.fixture(scope="session")
def app_version(run_local_app: Page) -> Version:
    """Desktop app software version from App Settings → General (session-scoped)."""
    settings = AppSettingsPage(run_local_app)
    log_step("Read App Software Version from App Settings")
    raw = settings.read_app_software_version()
    version = parse_app_version(raw)
    log_done(f"App software version: {raw!r} → {version}")
    # Leave later fixtures on Devices landing rather than stuck in Settings.
    navigate_to(run_local_app, "Devices", DevicesPage.DEVICES_LANDING_URL)
    return version


@pytest.fixture(scope="session")
def device_details_tabs(app_version: Version) -> bool:
    """True when Device Details uses Hardware / Deck Configuration / Run History tabs."""
    enabled = has_device_details_tabs(app_version)
    log_step(f"Device Details tabs layout: {enabled} (app {app_version})")
    return enabled


@pytest.fixture(autouse=True)
def _headed_bring_app_to_front(request: pytest.FixtureRequest, run_local_app: Page) -> Generator[None, None, None]:
    """Bring the Electron window to the front before each test in headed mode."""
    if is_headed_run(request.config):
        try:
            if not run_local_app.is_closed():
                run_local_app.bring_to_front()
        except Exception:
            if run_local_app.is_closed():
                pytest.fail("Opentrons app window closed before test started.")
            raise
    yield


@pytest.fixture(autouse=True)
def _record_test_artifacts(request: pytest.FixtureRequest, run_local_app: Page) -> Generator[None, None, None]:
    """Record per-test Playwright trace and optional headed screencast video."""
    slug = slugify_nodeid(request.node.nodeid)
    headed = is_headed_run(request.config)
    uses_suite_video = request.node.get_closest_marker("device_cards") is not None
    recording = start_test_recording(
        context=run_local_app.context,
        page=run_local_app,
        slug=slug,
        record_screencast=headed and not uses_suite_video,
    )
    yield
    artifacts = stop_test_recording(run_local_app.context, recording)
    from automation.app_helpers.test_progress import log_path

    if artifacts.trace_path is not None:
        request.node.user_properties.append(("trace_path", str(artifacts.trace_path)))
        log_path("Playwright trace", artifacts.trace_path, kind="trace")
    if artifacts.video_path is not None:
        request.node.user_properties.append(("video_path", str(artifacts.video_path)))
        log_path("Playwright video", artifacts.video_path, kind="video")


@pytest.fixture(scope="session")
def protocol_name() -> str:
    """Default protocol title used by navigation tests."""
    return DEFAULT_PROTOCOL_NAME


@pytest.fixture(scope="session")
def screenshot_helper(run_local_app: Page) -> ScreenshotHelper:
    """Session-scoped helper for saving PNG screenshots under ``artifacts/``."""
    return ScreenshotHelper(run_local_app)


def _artifact_extras(item: pytest.Item) -> list:
    """Build pytest-html extras for trace, video, and failure screenshot artifacts."""
    report_extras: list = []
    for name, path_str in item.user_properties:
        path = Path(path_str)
        if not path.exists():
            continue
        relative = path.as_posix()
        if name == "trace_path":
            report_extras.append(html_extras.url(relative, name="Playwright trace (open in trace viewer)"))
        elif name == "video_path":
            report_extras.append(
                html_extras.html(f'<video width="640" controls><source src="{relative}" type="video/webm"></video>')
            )
            report_extras.append(html_extras.url(relative, name="Download video"))
        elif name == "screenshot_path":
            report_extras.append(html_extras.image(relative))
    return report_extras


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Generator[None, Any, None]:
    """Attach trace, video, and failure screenshot links to the HTML report."""
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        page = item.funcargs.get("run_local_app")
        if page is not None:
            slug = slugify_nodeid(item.nodeid)
            screenshot_path = capture_failure_screenshot(page, slug)
            if screenshot_path is not None:
                item.user_properties.append(("screenshot_path", str(screenshot_path)))
    if report.when == "teardown":
        report.extras = getattr(report, "extras", []) + _artifact_extras(item)


def pytest_configure(config: pytest.Config) -> None:
    """Ensure the HTML report output directory exists for app tests."""
    ensure_test_results_dir()


# Full-suite order for ``make test-app``. Run setup remains last.
_MODULE_ORDER = (
    "device_cards/test_devices_nav.py",
    "device_cards/test_robot_settings.py",
    "device_cards/test_robot_settings_file_manager.py",
    "device_cards/test_cards.py",
    "device_cards/test_deck_configuration.py",
    "device_cards/test_run_history.py",
    "nav/test_labware.py",
    "nav/test_protocols.py",
    "nav/test_protocol_actions.py",
    "nav/test_app_settings.py",
    "nav/test_app_settings_placeholders.py",
    "calibration/test_calibration.py",
    "nav/test_protocol_run_tabs.py",
    "nav/test_run_setup.py",
)

# Within calibration: reset first, then status checks, then per-instrument wizards.
_CALIBRATION_TEST_ORDER = (
    "test_device_reset",
    "test_calibration_flow",
    "test_calibration_overflow_menu",
    "test_96_channel_calibration",
    "test_heater_shaker_calibration",
    "test_temperature_module_calibration",
    "test_thermocycler_calibration",
)

# Within robot settings: T69745–T69756 plan order (not alphabetical nodeid).
_ROBOT_SETTINGS_TEST_ORDER = (
    "test_calibration_about_calibration",
    "test_calibration_pipette_calibrations",
    "test_networking",
    "test_privacy",
    "test_advanced_robot_name",
    "test_advanced_robot_server_version",
    "test_advanced_pause_on_door_open",
    "test_home_gantry_from_overview_overflow",
    "test_advanced_jupyter_notebook",
    "test_advanced_update_robot_software",
    "test_advanced_robot_server_reinstall",
    "test_analytics",
)

_ABR_SUITE_DIR = "abr_orchestration"


def _is_app_test(item: pytest.Item) -> bool:
    """Return True when the test lives under ``tests/app/``."""
    parts = item.path.parts
    return "tests" in parts and "app" in parts and parts.index("tests") + 1 == parts.index("app")


def _is_abr_test(item: pytest.Item) -> bool:
    """Return True when the test lives under ``tests/app/abr_orchestration/``."""
    return _ABR_SUITE_DIR in item.path.parts


def _module_relpath(item: pytest.Item) -> str:
    """Return ``<suite>/<file>.py`` for sorting (e.g. ``calibration/test_calibration.py``)."""
    return "/".join(item.path.parts[-2:])


def pytest_collection_modifyitems(session: pytest.Session, config: pytest.Config, items: list[pytest.Item]) -> None:
    """Order the app suite and keep ABR out of mixed ``tests/app/`` runs."""
    del session

    app_items = [item for item in items if _is_app_test(item)]
    if not app_items:
        return

    abr_items = [item for item in app_items if _is_abr_test(item)]
    non_abr_app_items = [item for item in app_items if not _is_abr_test(item)]
    # Deselect ABR when other app suites are also collected (full ``test-app``).
    # Dedicated ``make run_abr_2_and_4`` only collects ABR, so those stay.
    if abr_items and non_abr_app_items:
        config.hook.pytest_deselected(items=abr_items)
        items[:] = [item for item in items if not _is_abr_test(item)]
        app_items = non_abr_app_items

    module_rank = {path: index for index, path in enumerate(_MODULE_ORDER)}
    calibration_rank = {name: index for index, name in enumerate(_CALIBRATION_TEST_ORDER)}
    robot_settings_rank = {name: index for index, name in enumerate(_ROBOT_SETTINGS_TEST_ORDER)}
    unknown_module = len(_MODULE_ORDER)
    unknown_calibration = len(_CALIBRATION_TEST_ORDER)
    unknown_robot_settings = len(_ROBOT_SETTINGS_TEST_ORDER)

    def sort_key(item: pytest.Item) -> tuple[int, int, str]:
        module = _module_relpath(item)
        if module == "calibration/test_calibration.py":
            test_rank = calibration_rank.get(item.name, unknown_calibration)
        elif module == "device_cards/test_robot_settings.py":
            test_rank = robot_settings_rank.get(item.name, unknown_robot_settings)
        else:
            test_rank = 0
        return (module_rank.get(module, unknown_module), test_rank, item.nodeid)

    app_indices = [index for index, item in enumerate(items) if _is_app_test(item)]
    ordered = sorted((items[index] for index in app_indices), key=sort_key)
    for index, item in zip(app_indices, ordered, strict=True):
        items[index] = item


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Ensure artifact directories exist before pytest-html writes the report."""
    ensure_test_results_dir()

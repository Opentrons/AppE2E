"""App Settings gear menu tabs.

App Settings test plan (``nav`` suite — runs after ``device_cards``):

1. T69757 — App Settings > Feature flags
2. T69758 — App Settings > General > Connect to a Robot via IP Address
3. T69848 — App settings > Privacy > Share App Analytics with Opentrons
4. T69760 — App Settings > Advanced > Update Channel
5. T69761 — App Settings > Advanced > Additional Custom Labware Source Folder
6. T69762 — App Settings > Advanced > Display Unavailable Robots
7. T69763 — App Settings > Advanced > Clear Unavailable Robots
8. T69764 — App Settings > Advanced > Enable Developer Tool
9. T69765 — App Settings > General > Update
10. T69766 — App Settings > General > Software Update Alerts
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from automation.app_helpers.screenshot_helper import ScreenshotHelper
from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages import AppSettingsPage


@pytest.mark.workflow(
    group="app_settings",
    section="General",
    label="General settings",
    order=10,
    cases=(
        ("T69758", "Connect to a Robot via IP Address"),
        ("T69765", "Update"),
        ("T69766", "Software Update Alerts"),
    ),
)
def test_general_tab(run_local_app: Page, screenshot_helper: ScreenshotHelper) -> None:
    """T69758, T69765, T69766: General tab settings.

    Validates connect via IP (T69758), software version/update (T69765), and
    software update alerts toggle (T69766).
    """
    log_step("Open App Settings")
    settings = AppSettingsPage(run_local_app, shots=screenshot_helper)
    settings.navigate()
    log_step("Validate General tab")
    settings.validate_general()
    screenshot_helper.capture("app_settings", "general")
    log_done("General tab OK")


@pytest.mark.workflow(
    group="app_settings",
    section="Privacy",
    label="Privacy settings",
    order=20,
    cases=(("T69848", "Share App Analytics with Opentrons"),),
)
def test_privacy_tab(run_local_app: Page, screenshot_helper: ScreenshotHelper) -> None:
    """T69848: Privacy > Share App Analytics with Opentrons."""
    log_step("Open App Settings")
    settings = AppSettingsPage(run_local_app, shots=screenshot_helper)
    settings.navigate()
    log_step("Validate Privacy tab")
    settings.validate_privacy()
    screenshot_helper.capture("app_settings", "privacy")
    log_done("Privacy tab OK")


@pytest.mark.workflow(
    group="app_settings",
    section="Advanced",
    label="Advanced settings",
    order=30,
    cases=(
        ("T69760", "Update Channel"),
        ("T69761", "Additional Custom Labware Source Folder"),
        ("T69762", "Display Unavailable Robots"),
        ("T69763", "Clear Unavailable Robots"),
        ("T69764", "Enable Developer Tool"),
    ),
)
def test_advanced_tab(run_local_app: Page, screenshot_helper: ScreenshotHelper) -> None:
    """T69760–T69764: Advanced tab settings.

    Validates update channel (T69760), custom labware folder (T69761),
    prevent robot caching / unavailable robots (T69762), clear unavailable
    robots (T69763), and developer tools (T69764).
    """
    log_step("Open App Settings")
    settings = AppSettingsPage(run_local_app, shots=screenshot_helper)
    settings.navigate()
    log_step("Validate Advanced tab")
    settings.validate_advanced()
    screenshot_helper.capture("app_settings", "advanced")
    log_done("Advanced tab OK")


@pytest.mark.workflow(
    group="app_settings",
    section="Feature Flags",
    label="Feature Flags",
    order=40,
    cases=(("T69757", "Feature flags"),),
)
def test_feature_flags_tab(run_local_app: Page, screenshot_helper: ScreenshotHelper) -> None:
    """T69757: App Settings > Feature flags."""
    log_step("Open App Settings")
    settings = AppSettingsPage(run_local_app, shots=screenshot_helper)
    settings.navigate()
    if settings.tab_link(settings.FEATURE_FLAGS_TAB).count() == 0:
        log_step("Feature Flags tab not present — skipping")
        pytest.skip("Feature Flags tab not present.")
    log_step("Validate Feature Flags tab")
    settings.validate_feature_flags()
    screenshot_helper.capture("app_settings", "feature_flags")
    log_done("Feature Flags tab OK")

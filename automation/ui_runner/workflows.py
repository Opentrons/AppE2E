"""Workflow grouping and default metadata for the selectable E2E catalog.

Tabs in ``make ui`` (APP is home):
  APP → APP CRS → ODD → ODD CRS

APP CRS shows Compliance Ready setup plus the same app workflow groups as APP,
backed by ``tests/compliance/admin_walk/crs_app/`` mirrors that run logged in as
Admin (``crs_login``). Within each tab, group order follows ``TEST_FLOWS_APP.md``
/ ``TEST_FLOWS_ODD.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CatalogTab = Literal["app", "app_crs", "odd", "odd_crs"]

CATALOG_TABS: tuple[tuple[CatalogTab, str], ...] = (
    ("app", "APP"),
    ("app_crs", "APP CRS"),
    ("odd", "ODD"),
    ("odd_crs", "ODD CRS"),
)


@dataclass(frozen=True)
class WorkflowGroup:
    id: str
    label: str
    order: int
    tab: CatalogTab
    collapsible: bool = False


WORKFLOW_GROUPS = (
    # APP
    WorkflowGroup("devices", "Devices", 10, "app"),
    WorkflowGroup("robot_settings", "Robot settings", 20, "app"),
    WorkflowGroup("app_settings", "App settings", 30, "app"),
    WorkflowGroup("protocols", "Protocol page", 40, "app"),
    WorkflowGroup("labware", "Labware", 50, "app"),
    WorkflowGroup("protocol_run", "Protocol run", 60, "app"),
    WorkflowGroup("run_setup", "Protocol setup", 70, "app"),
    WorkflowGroup("calibration", "Calibration", 80, "app"),
    WorkflowGroup("abr", "ABR start-run", 90, "app"),
    # APP CRS — enable/login/user setup. Mirrored tests/app cases keep their
    # original group ids and are routed to this tab via the crs_login mark.
    WorkflowGroup("compliance", "Compliance Ready", 5, "app_crs"),
    WorkflowGroup("compliance_testing", "Compliance Ready Testing", 6, "app_crs"),
    # ODD
    WorkflowGroup("odd_protocols", "ODD protocols", 10, "odd"),
    WorkflowGroup("odd_settings", "ODD settings", 20, "odd"),
    WorkflowGroup("odd_deck", "ODD deck", 30, "odd"),
    WorkflowGroup("odd_instruments", "ODD instruments", 40, "odd"),
    WorkflowGroup("odd_device_reset", "ODD device reset", 50, "odd"),
    WorkflowGroup("odd_update", "ODD update", 60, "odd"),
)

GROUP_BY_ID = {group.id: group for group in WORKFLOW_GROUPS}

# Paths collected into the selectable UI catalog.
CATALOG_PATHS = ("tests/app", "tests/odd", "tests/compliance")

# Present under ``tests/compliance`` but not selectable. The recorder pauses
# until someone closes Playwright Inspector. The documentation checks are
# skipped stubs and have no workflow metadata yet.
CATALOG_IGNORES = (
    "tests/compliance/example_test.py",
    "tests/compliance/test_documentation_required.py",
)


def catalog_pytest_args() -> list[str]:
    """Paths and ignores for ``pytest --collect-only`` of the make-ui catalog."""
    args = list(CATALOG_PATHS)
    args.extend(f"--ignore={path}" for path in CATALOG_IGNORES)
    return args

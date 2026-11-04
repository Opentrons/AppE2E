"""Workflow grouping and default metadata for the selectable E2E catalog.

Group order follows the desktop suite flow in ``TEST_FLOWS_APP.md``, then
ODD groups from ``TEST_FLOWS_ODD.md``:
Devices → Robot Settings → Compliance Ready → App Settings → Protocols →
Labware → Protocol run → Setup steps → Calibration → ABR →
ODD protocols → ODD settings → ODD deck → ODD instruments →
ODD device reset → ODD update.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowGroup:
    id: str
    label: str
    order: int


WORKFLOW_GROUPS = (
    WorkflowGroup("devices", "Devices", 10),
    WorkflowGroup("robot_settings", "Robot settings", 20),
    WorkflowGroup("compliance", "Compliance Ready", 25),
    WorkflowGroup("app_settings", "App settings", 30),
    WorkflowGroup("protocols", "Protocol page", 40),
    WorkflowGroup("labware", "Labware", 50),
    WorkflowGroup("protocol_run", "Protocol run", 60),
    WorkflowGroup("run_setup", "Protocol setup", 70),
    WorkflowGroup("calibration", "Calibration", 80),
    WorkflowGroup("abr", "ABR start-run", 90),
    WorkflowGroup("odd_protocols", "ODD protocols", 100),
    WorkflowGroup("odd_settings", "ODD settings", 110),
    WorkflowGroup("odd_deck", "ODD deck", 120),
    WorkflowGroup("odd_instruments", "ODD instruments", 130),
    WorkflowGroup("odd_device_reset", "ODD device reset", 140),
    WorkflowGroup("odd_update", "ODD update", 150),
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

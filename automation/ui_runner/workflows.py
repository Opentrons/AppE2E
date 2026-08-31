"""Workflow grouping and default metadata for the selectable E2E catalog."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowGroup:
    id: str
    label: str
    order: int


WORKFLOW_GROUPS = (
    WorkflowGroup("app_settings", "App settings", 10),
    WorkflowGroup("labware", "Labware", 20),
    WorkflowGroup("devices", "Devices", 30),
    WorkflowGroup("robot_settings", "Robot settings", 40),
    WorkflowGroup("protocols", "Protocol page", 50),
    WorkflowGroup("protocol_run", "Protocol run", 60),
    WorkflowGroup("run_setup", "Setup last", 70),
)

GROUP_BY_ID = {group.id: group for group in WORKFLOW_GROUPS}

"""Pytest plugin that exports workflow metadata as a JSON manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from automation.ui_runner.workflows import GROUP_BY_ID, WORKFLOW_GROUPS

REQUIRED_WORKFLOW_FIELDS = frozenset({"group", "section", "label", "order"})
OPTIONAL_WORKFLOW_FIELDS = frozenset({"requires", "cases"})


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--e2e-manifest", action="store", default=None, help="Write the selectable E2E catalog to PATH.")


def _normalize_cases(item: pytest.Item, raw: object) -> list[dict[str, str]]:
    """Accept ``((id, title), ...)`` and return ``[{id, title}, ...]``."""
    if raw is None:
        return []
    if not isinstance(raw, (list, tuple)):
        raise pytest.UsageError(
            f"{item.nodeid}: workflow 'cases' must be a sequence of (id, title) pairs"
        )
    cases: list[dict[str, str]] = []
    for entry in raw:
        case_id: str | None = None
        title: str | None = None
        if isinstance(entry, (list, tuple)) and len(entry) == 2:
            case_id, title = str(entry[0]).strip(), str(entry[1]).strip()
        elif isinstance(entry, dict):
            case_id = str(entry.get("id", "")).strip()
            title = str(entry.get("title", "")).strip()
        if not case_id or not title:
            raise pytest.UsageError(
                f"{item.nodeid}: each workflow case must be (id, title) with non-empty strings"
            )
        cases.append({"id": case_id, "title": title})
    return cases


def _workflow_metadata(item: pytest.Item, marker: pytest.Mark) -> dict[str, Any]:
    if marker.args:
        raise pytest.UsageError(f"{item.nodeid}: workflow metadata must use keyword arguments")
    unknown = marker.kwargs.keys() - REQUIRED_WORKFLOW_FIELDS - OPTIONAL_WORKFLOW_FIELDS
    missing = REQUIRED_WORKFLOW_FIELDS - marker.kwargs.keys()
    if unknown or missing:
        raise pytest.UsageError(
            f"{item.nodeid}: invalid workflow fields (missing={sorted(missing)}, unknown={sorted(unknown)})"
        )

    metadata = dict(marker.kwargs)
    for field in ("group", "section", "label"):
        if not isinstance(metadata[field], str) or not metadata[field].strip():
            raise pytest.UsageError(f"{item.nodeid}: workflow {field!r} must be a non-empty string")
    if not isinstance(metadata["order"], int) or isinstance(metadata["order"], bool):
        raise pytest.UsageError(f"{item.nodeid}: workflow 'order' must be an integer")
    requires = metadata.get("requires")
    if requires is not None and (not isinstance(requires, str) or not requires.strip()):
        raise pytest.UsageError(f"{item.nodeid}: workflow 'requires' must be a non-empty node id or None")
    metadata["cases"] = _normalize_cases(item, metadata.get("cases"))
    return metadata


def _serialize_item(item: pytest.Item) -> dict[str, Any] | None:
    marker = item.get_closest_marker("workflow")
    if marker is None:
        if item.nodeid.startswith("tests/app/"):
            raise pytest.UsageError(f"{item.nodeid}: missing required workflow marker")
        return None
    metadata = _workflow_metadata(item, marker)
    group_id = metadata["group"]
    if group_id not in GROUP_BY_ID:
        raise pytest.UsageError(f"{item.nodeid}: unknown workflow group {group_id!r}")
    skip = item.get_closest_marker("skip")
    skip_reason = None
    if skip is not None:
        skip_reason = skip.kwargs.get("reason")
        if skip_reason is None and skip.args:
            skip_reason = str(skip.args[0])
    file_path, lineno, _ = item.location
    relative_file = Path(file_path).as_posix()
    try:
        relative_file = Path(file_path).resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        pass
    return {
        "node_id": item.nodeid,
        "group": group_id,
        "section": metadata["section"],
        "label": metadata["label"],
        "order": metadata["order"],
        "requires": metadata.get("requires"),
        "cases": metadata.get("cases") or [],
        "implemented": skip is None,
        "placeholder": skip is not None,
        "skip_reason": skip_reason,
        "file": relative_file,
        "line": None if lineno is None else int(lineno) + 1,
    }


def _validate_prerequisites(tests: list[dict[str, Any]]) -> None:
    requirements = {test["node_id"]: test["requires"] for test in tests}
    missing = [
        (node_id, required) for node_id, required in requirements.items() if required and required not in requirements
    ]
    if missing:
        details = ", ".join(f"{node_id} -> {required}" for node_id, required in missing)
        raise pytest.UsageError(f"Workflow prerequisites are absent from the manifest: {details}")

    for start in requirements:
        chain: list[str] = []
        current: str | None = start
        while current is not None:
            if current in chain:
                cycle = chain[chain.index(current) :] + [current]
                raise pytest.UsageError(f"Workflow prerequisite cycle: {' -> '.join(cycle)}")
            chain.append(current)
            current = requirements[current]


def pytest_collection_finish(session: pytest.Session) -> None:
    destination = session.config.getoption("--e2e-manifest")
    if not destination:
        return
    tests = [entry for item in session.items if (entry := _serialize_item(item)) is not None]
    _validate_prerequisites(tests)
    group_order = {group.id: group.order for group in WORKFLOW_GROUPS}
    tests.sort(key=lambda test: (group_order[test["group"]], test["section"], test["order"], test["node_id"]))
    payload = {
        "groups": [{"id": group.id, "label": group.label, "order": group.order} for group in WORKFLOW_GROUPS],
        "tests": tests,
    }
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

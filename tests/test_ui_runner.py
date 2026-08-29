"""Focused unit tests for the workflow runner backend."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from automation.app_helpers.test_progress import log_done, log_step, run_timed, set_event_sink
from automation.ui_runner.collect_plugin import _validate_prerequisites
from automation.ui_runner.event_plugin import EventWriter
from automation.ui_runner.server import ROOT, WorkflowCatalog, app, resolve_repo_path


def _catalog(tmp_path: Path) -> WorkflowCatalog:
    catalog = WorkflowCatalog(tmp_path)
    catalog._payload = {
        "groups": [],
        "tests": [
            {
                "node_id": "tests/test_example.py::test_setup",
                "implemented": True,
                "requires": None,
            },
            {
                "node_id": "tests/test_example.py::test_workflow",
                "implemented": True,
                "requires": "tests/test_example.py::test_setup",
            },
            {
                "node_id": "tests/test_example.py::test_placeholder",
                "implemented": False,
                "requires": None,
            },
        ],
    }
    return catalog


def test_catalog_resolves_prerequisite_once(tmp_path: Path) -> None:
    resolved = asyncio.run(
        _catalog(tmp_path).resolve(
            [
                "tests/test_example.py::test_workflow",
                "tests/test_example.py::test_workflow",
            ]
        )
    )
    assert resolved == [
        "tests/test_example.py::test_setup",
        "tests/test_example.py::test_workflow",
    ]


def test_catalog_rejects_unknown_tests(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown test node IDs"):
        asyncio.run(_catalog(tmp_path).resolve(["tests/test_example.py::test_unknown"]))


def test_catalog_allows_safe_skipped_placeholder(tmp_path: Path) -> None:
    resolved = asyncio.run(_catalog(tmp_path).resolve(["tests/test_example.py::test_placeholder"]))
    assert resolved == ["tests/test_example.py::test_placeholder"]


def test_manifest_rejects_prerequisite_cycles() -> None:
    tests = [
        {"node_id": "tests/test_example.py::test_one", "requires": "tests/test_example.py::test_two"},
        {"node_id": "tests/test_example.py::test_two", "requires": "tests/test_example.py::test_one"},
    ]
    with pytest.raises(pytest.UsageError, match="prerequisite cycle"):
        _validate_prerequisites(tests)


def test_event_writer_adds_test_context_and_ndjson(tmp_path: Path) -> None:
    destination = tmp_path / "events.ndjson"
    writer = EventWriter(destination)
    writer.set_current_test("tests/test_example.py::test_workflow")
    writer.emit({"type": "step_start", "label": "Open app"})
    writer.set_current_test(None)
    writer.emit({"type": "session_end", "exit_status": 0})

    events = [json.loads(line) for line in destination.read_text(encoding="utf-8").splitlines()]
    assert events[0]["node_id"] == "tests/test_example.py::test_workflow"
    assert events[0]["type"] == "step_start"
    assert "node_id" not in events[1]


def test_progress_output_is_preserved_with_structured_sink(capsys: pytest.CaptureFixture[str]) -> None:
    events: list[dict[str, object]] = []
    set_event_sink(events.append)
    try:
        log_step("Open app")
        log_done("App opened")
        run_timed("Click Devices", lambda: None)
    finally:
        set_event_sink(None)

    output = capsys.readouterr().out
    assert "-> Open app" in output
    assert "[ok] App opened" in output
    assert [event["type"] for event in events] == ["step_start", "step_done", "step_start", "step_done"]
    for event in events:
        assert event["file"] == "tests/test_ui_runner.py"
        assert isinstance(event["line"], int)
        assert event["line"] > 0


def test_resolve_repo_path_rejects_escapes() -> None:
    with pytest.raises(ValueError, match="relative"):
        resolve_repo_path("/etc/passwd")
    with pytest.raises(ValueError, match="relative"):
        resolve_repo_path("../secrets.py")


def test_source_api_returns_highlighted_file() -> None:
    client = TestClient(app)
    relative = Path("tests/test_ui_runner.py").as_posix()
    response = client.get("/api/source", params={"path": relative, "line": 1})
    assert response.status_code == 200
    payload = response.json()
    assert payload["path"] == relative
    assert payload["absolute_path"] == str((ROOT / relative).resolve())
    assert payload["line"] == 1
    assert "Focused unit tests" in payload["content"]
    assert payload["line_count"] > 0


def test_source_api_rejects_missing_and_unsafe_paths() -> None:
    client = TestClient(app)
    missing = client.get("/api/source", params={"path": "tests/does_not_exist.py"})
    assert missing.status_code == 404
    unsafe = client.get("/api/source", params={"path": "../README.md"})
    assert unsafe.status_code == 400

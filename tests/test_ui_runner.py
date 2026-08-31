"""Focused unit tests for the workflow runner backend."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from automation.app_helpers.test_progress import log_done, log_step, run_timed, set_event_sink
from automation.ui_runner.collect_plugin import _validate_prerequisites
from automation.ui_runner.event_plugin import EventWriter
from automation.ui_runner.server import ROOT, WorkflowCatalog, _upsert_env_keys, app, resolve_repo_path


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


def test_event_writer_survives_a_wiped_results_directory(tmp_path: Path) -> None:
    destination = tmp_path / "results" / "events.ndjson"
    writer = EventWriter(destination)
    writer.emit({"type": "session_start"})
    shutil.rmtree(destination.parent)

    writer.emit({"type": "test_end", "status": "passed"})

    events = [json.loads(line) for line in destination.read_text(encoding="utf-8").splitlines()]
    assert [event["type"] for event in events] == ["test_end"]


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


def test_defaults_api_returns_robot_and_protocol(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("ROBOT_NAME=UIRobot\nPROTOCOL_NAME=UI Protocol\n", encoding="utf-8")
    monkeypatch.setattr("automation.ui_runner.server.ENV_PATH", env_path)
    monkeypatch.delenv("ROBOT_NAME", raising=False)
    monkeypatch.delenv("PROTOCOL_NAME", raising=False)

    client = TestClient(app)
    response = client.get("/api/defaults")
    assert response.status_code == 200
    assert response.json() == {"robot_name": "UIRobot", "protocol_name": "UI Protocol"}


def test_upsert_env_keys_preserves_unrelated_entries(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "# keep me\nROBOT_NAME=Old\nROBOT_IP=10.0.0.1\nOPENTRONS_ROOT=/tmp/opentrons\n",
        encoding="utf-8",
    )
    _upsert_env_keys({"ROBOT_NAME": "NewRobot", "PROTOCOL_NAME": "Smoke"}, path=env_path)
    text = env_path.read_text(encoding="utf-8")
    assert "# keep me" in text
    assert "ROBOT_NAME=NewRobot" in text
    assert "PROTOCOL_NAME=Smoke" in text
    assert "ROBOT_IP=10.0.0.1" in text
    assert "OPENTRONS_ROOT=/tmp/opentrons" in text


def test_run_api_requires_robot_and_protocol_names() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/run",
        json={"node_ids": ["tests/test_example.py::test_setup"], "flex_ready": False, "headed": True},
    )
    assert response.status_code == 422

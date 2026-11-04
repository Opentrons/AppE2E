"""Focused unit tests for the workflow runner backend."""

from __future__ import annotations

import asyncio
import json
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from automation.app_helpers.crs_accounts import (
    CrsReportedAccount,
    load_saved_credentials_event,
    save_crs_accounts,
)
from automation.app_helpers.test_progress import log_done, log_step, run_timed, set_event_sink
from automation.ui_runner.collect_plugin import _validate_prerequisites
from automation.ui_runner.event_plugin import EventWriter
from automation.ui_runner.server import (
    DEFAULT_APP_PATH,
    ROOT,
    EventStream,
    WorkflowCatalog,
    _upsert_env_keys,
    app,
    normalize_app_path,
    resolve_repo_path,
)


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


def test_crs_accounts_persist_until_overwrite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "crs_accounts.json"
    monkeypatch.setattr("automation.app_helpers.crs_accounts.CRS_ACCOUNTS_PATH", path)
    accounts = (
        CrsReportedAccount(role="Service", username="service", password="aaa-bbb-ccc-ddd"),
        CrsReportedAccount(role="Admin", username="testadmin", password="testadminpassword", legal_name="test admin"),
    )
    save_crs_accounts(accounts, service_pin="SERIAL-0000")
    loaded = load_saved_credentials_event()
    assert loaded is not None
    assert loaded["service_pin"] == "SERIAL-0000"
    assert loaded["accounts"][0]["password"] == "aaa-bbb-ccc-ddd"

    stream = EventStream()
    assert stream.latest_credentials == loaded
    stream._remember({"type": "session_start"})
    assert stream.latest_credentials == loaded

    replacement = {
        "type": "credentials",
        "service_pin": "NEW-0000",
        "accounts": [{"role": "Service", "username": "service", "password": "zzz-yyy-xxx-www", "legal_name": ""}],
    }
    stream._remember(replacement)
    assert stream.latest_credentials == replacement


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
    env_path.write_text(
        "ROBOT_NAME=UIRobot\nPROTOCOL_NAME=UI Protocol\nROBOT_IP=10.14.19.200\nOPENTRONS_APP_PATH=/tmp/Opentrons\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("automation.ui_runner.server.ENV_PATH", env_path)
    monkeypatch.delenv("ROBOT_NAME", raising=False)
    monkeypatch.delenv("PROTOCOL_NAME", raising=False)
    monkeypatch.delenv("ROBOT_IP", raising=False)
    monkeypatch.delenv("OPENTRONS_APP_PATH", raising=False)

    client = TestClient(app)
    response = client.get("/api/defaults")
    assert response.status_code == 200
    assert response.json() == {
        "robot_name": "UIRobot",
        "protocol_name": "UI Protocol",
        "robot_ip": "10.14.19.200",
        "app_path": "/tmp/Opentrons",
    }


def test_defaults_api_falls_back_to_installed_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("ROBOT_NAME=UIRobot\n", encoding="utf-8")
    monkeypatch.setattr("automation.ui_runner.server.ENV_PATH", env_path)
    monkeypatch.delenv("ROBOT_NAME", raising=False)
    monkeypatch.delenv("PROTOCOL_NAME", raising=False)
    monkeypatch.delenv("ROBOT_IP", raising=False)
    monkeypatch.delenv("OPENTRONS_APP_PATH", raising=False)

    client = TestClient(app)
    response = client.get("/api/defaults")
    assert response.status_code == 200
    assert response.json()["app_path"] == DEFAULT_APP_PATH


def test_normalize_app_path_requires_an_existing_file(tmp_path: Path) -> None:
    executable = tmp_path / "Opentrons"
    executable.write_bytes(b"")
    assert normalize_app_path(f' "{executable}" ') == str(executable)
    with pytest.raises(ValueError, match="not a file"):
        normalize_app_path(str(tmp_path / "missing"))


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


def test_prompt_api_writes_the_answer_and_clears_the_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from automation.ui_runner.server import event_stream, runner

    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    monkeypatch.setattr(runner, "prompt_dir", prompt_dir)
    event_stream.pending_prompt = {"type": "prompt", "prompt_id": "a" * 32, "title": "Robot encryption key"}
    client = TestClient(app)
    try:
        response = client.post("/api/prompt", json={"prompt_id": "a" * 32, "value": " bouquet-nuclear-figurine "})
        assert response.status_code == 200
        assert response.json() == {"status": "accepted"}
        saved = json.loads((prompt_dir / f"{'a' * 32}.json").read_text(encoding="utf-8"))
        assert saved == {"value": "bouquet-nuclear-figurine"}
        assert event_stream.pending_prompt is None
    finally:
        monkeypatch.undo()
        event_stream.pending_prompt = None


def test_prompt_api_rejects_a_missing_run_and_a_bad_id() -> None:
    from automation.ui_runner.server import runner

    client = TestClient(app)
    assert runner.prompt_dir is None
    missing = client.post("/api/prompt", json={"prompt_id": "a" * 32, "value": "word-word-word"})
    assert missing.status_code == 409
    bad_id = client.post("/api/prompt", json={"prompt_id": "../secret", "value": "word-word-word"})
    assert bad_id.status_code == 400


def test_request_text_reads_the_runner_answer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import threading

    from automation.app_helpers.test_progress import set_event_sink
    from automation.app_helpers.ui_prompt import request_text

    monkeypatch.setenv("E2E_PROMPT_DIR", str(tmp_path))
    events: list[dict[str, object]] = []
    set_event_sink(events.append)

    def answer() -> None:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not events:
            time.sleep(0.02)
        prompt_id = str(events[0]["prompt_id"])
        (tmp_path / f"{prompt_id}.json").write_text(
            json.dumps({"value": "bouquet-nuclear-figurine"}),
            encoding="utf-8",
        )

    threading.Thread(target=answer, daemon=True).start()
    try:
        assert request_text(title="Robot encryption key", message="Type the key on the robot.", timeout_s=5) == (
            "bouquet-nuclear-figurine"
        )
    finally:
        set_event_sink(None)

    assert events[0]["type"] == "prompt"
    assert events[0]["title"] == "Robot encryption key"


def test_spa_routes_serve_index() -> None:
    client = TestClient(app)
    for path in ("/", "/run"):
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Workflow test runner" in response.text
        assert 'data-nav="setup"' in response.text
        assert 'data-nav="run"' in response.text
        assert 'id="app-path"' in response.text
        assert 'id="operator-prompt"' in response.text
        assert 'id="crs-accounts"' in response.text

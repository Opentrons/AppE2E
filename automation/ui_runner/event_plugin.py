"""Pytest plugin emitting newline-delimited JSON progress events."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Generator

import pytest

from automation.app_helpers.test_progress import set_event_sink

_active_writer: EventWriter | None = None


class EventWriter:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.path.write_text("", encoding="utf-8")
        self._lock = threading.Lock()
        self._node_id: str | None = None

    def set_current_test(self, node_id: str | None) -> None:
        with self._lock:
            self._node_id = node_id

    def emit(self, event: dict[str, object]) -> None:
        payload = {"timestamp": time.time(), **event}
        with self._lock:
            if self._node_id is not None:
                payload.setdefault("node_id", self._node_id)
        with self._lock, self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, default=str) + "\n")
            stream.flush()


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--e2e-events", action="store", default=None, help="Write NDJSON progress events to PATH.")


def _writer(config: pytest.Config) -> EventWriter | None:
    return getattr(config, "_e2e_event_writer", None)


def pytest_configure(config: pytest.Config) -> None:
    global _active_writer
    destination = config.getoption("--e2e-events")
    if not destination:
        return
    writer = EventWriter(Path(destination))
    setattr(config, "_e2e_event_writer", writer)
    _active_writer = writer
    set_event_sink(writer.emit)


def pytest_unconfigure(config: pytest.Config) -> None:
    global _active_writer
    if _writer(config) is not None:
        _active_writer = None
        set_event_sink(None)


def pytest_sessionstart(session: pytest.Session) -> None:
    writer = _writer(session.config)
    if writer:
        writer.emit({"type": "session_start"})


def pytest_collection_finish(session: pytest.Session) -> None:
    writer = _writer(session.config)
    if writer is None:
        return
    cache: dict[str, list[dict[str, str]]] = {}
    for item in session.items:
        marker = item.get_closest_marker("workflow")
        cases: list[dict[str, str]] = []
        if marker is not None:
            for entry in marker.kwargs.get("cases") or ():
                if isinstance(entry, (list, tuple)) and len(entry) == 2:
                    case_id, title = str(entry[0]).strip(), str(entry[1]).strip()
                    if case_id and title:
                        cases.append({"id": case_id, "title": title})
                elif isinstance(entry, dict):
                    case_id = str(entry.get("id", "")).strip()
                    title = str(entry.get("title", "")).strip()
                    if case_id and title:
                        cases.append({"id": case_id, "title": title})
        cache[item.nodeid] = cases
    setattr(writer, "_cases_by_node", cache)


def pytest_runtest_logstart(nodeid: str, location: tuple[str, int, str]) -> None:
    if _active_writer:
        file_path, lineno, _ = location
        relative_file = Path(file_path).as_posix()
        try:
            relative_file = Path(file_path).resolve().relative_to(Path.cwd().resolve()).as_posix()
        except ValueError:
            pass
        cases = getattr(_active_writer, "_cases_by_node", {}).get(nodeid, [])
        _active_writer.set_current_test(nodeid)
        _active_writer.emit(
            {
                "type": "test_start",
                "node_id": nodeid,
                "label": nodeid.rsplit("::", 1)[-1],
                "file": relative_file,
                "line": None if lineno is None else int(lineno) + 1,
                "cases": cases,
            }
        )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Generator[None, Any, None]:
    del call
    outcome = yield
    report = outcome.get_result()
    reports = getattr(item, "_e2e_reports", {})
    reports[report.when] = report
    setattr(item, "_e2e_reports", reports)
    if report.when != "teardown":
        return

    writer = _writer(item.config)
    if writer is None:
        return
    phases = list(reports.values())
    if any(phase.failed for phase in phases):
        status = "failed"
    elif any(phase.skipped for phase in phases):
        status = "skipped"
    else:
        status = "passed"
    artifacts: dict[str, str] = {}
    root = Path.cwd().resolve()
    for name, value in item.user_properties:
        if name not in {"trace_path", "video_path", "screenshot_path"}:
            continue
        artifact_path = Path(str(value)).resolve()
        try:
            artifacts[name] = artifact_path.relative_to(root).as_posix()
        except ValueError:
            continue
    writer.emit(
        {
            "type": "test_end",
            "node_id": item.nodeid,
            "status": status,
            "duration": sum(float(phase.duration) for phase in phases),
            "artifacts": artifacts,
        }
    )
    for kind, path in artifacts.items():
        writer.emit({"type": "artifact", "node_id": item.nodeid, "kind": kind, "path": path})
    writer.set_current_test(None)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    writer = _writer(session.config)
    if writer:
        writer.emit({"type": "session_end", "exit_status": exitstatus})

"""FastAPI application for selecting and running workflow-tagged pytest cases."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(__file__).with_name("static")
RESULTS_DIR = ROOT / "test-results"
ARTIFACTS_DIR = ROOT / "artifacts"
ENV_PATH = ROOT / ".env"
DEFAULT_PROTOCOL_NAME = "Flex Smoke Test"


def _load_env_file(path: Path | None = None) -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file (comments and blanks ignored)."""
    target = ENV_PATH if path is None else path
    if not target.exists():
        return {}
    values: dict[str, str] = {}
    for line in target.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _upsert_env_keys(updates: dict[str, str], path: Path | None = None) -> None:
    """Update or append keys in ``.env`` while preserving unrelated lines."""
    target = ENV_PATH if path is None else path
    existing_lines = target.read_text(encoding="utf-8").splitlines() if target.exists() else []
    remaining = dict(updates)
    rewritten: list[str] = []
    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                rewritten.append(f"{key}={remaining.pop(key)}")
                continue
        rewritten.append(line)
    if remaining:
        if rewritten and rewritten[-1] != "":
            rewritten.append("")
        for key, value in remaining.items():
            rewritten.append(f"{key}={value}")
    target.write_text("\n".join(rewritten) + "\n", encoding="utf-8")


def resolve_run_defaults() -> dict[str, str]:
    """Defaults for robot/protocol fields: process env, then .env, then built-ins."""
    from automation.app_helpers.robot_profiles import DEFAULT_HARDWARE_ROBOT_NAME

    file_values = _load_env_file()
    robot_name = (
        os.environ.get("ROBOT_NAME", "").strip()
        or file_values.get("ROBOT_NAME", "").strip()
        or DEFAULT_HARDWARE_ROBOT_NAME
    )
    protocol_name = (
        os.environ.get("PROTOCOL_NAME", "").strip()
        or file_values.get("PROTOCOL_NAME", "").strip()
        or DEFAULT_PROTOCOL_NAME
    )
    return {"robot_name": robot_name, "protocol_name": protocol_name}


def resolve_repo_path(relative_path: str) -> Path:
    """Resolve a repo-relative path and reject escapes outside the workspace root."""
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("Source path must be relative and stay inside the repository.")
    resolved = (ROOT / candidate).resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as error:
        raise ValueError("Source path must stay inside the repository.") from error
    if not resolved.is_file():
        raise FileNotFoundError(f"Source file not found: {relative_path}")
    return resolved


class RunRequest(BaseModel):
    node_ids: list[str] = Field(min_length=1)
    robot_name: str = Field(min_length=1)
    protocol_name: str = Field(min_length=1)
    flex_ready: bool = False
    headed: bool = True


class WorkflowCatalog:
    """Collect, cache, group, and validate selectable pytest node IDs."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._payload: dict[str, Any] | None = None
        self._lock = asyncio.Lock()

    async def load(self, *, refresh: bool = False) -> dict[str, Any]:
        async with self._lock:
            if self._payload is not None and not refresh:
                return self._payload
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as manifest:
                destination = Path(manifest.name)
            command = [
                sys.executable,
                "-m",
                "pytest",
                "tests/app",
                "--collect-only",
                "-q",
                "-p",
                "automation.ui_runner.collect_plugin",
                f"--e2e-manifest={destination}",
                "-o",
                "addopts=",
            ]
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=self.root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await process.communicate()
            try:
                if process.returncode not in (0, 5) or not destination.exists():
                    detail = stdout.decode(errors="replace")
                    raise RuntimeError(f"pytest collection failed ({process.returncode}):\n{detail}")
                self._payload = json.loads(destination.read_text(encoding="utf-8"))
            finally:
                destination.unlink(missing_ok=True)
            return self._payload

    async def resolve(self, selected: list[str]) -> list[str]:
        payload = await self.load()
        tests = {test["node_id"]: test for test in payload["tests"]}
        unknown = [node_id for node_id in selected if node_id not in tests]
        if unknown:
            raise ValueError(f"Unknown test node IDs: {unknown}")
        resolved = list(dict.fromkeys(selected))
        index = 0
        while index < len(resolved):
            required = tests[resolved[index]].get("requires")
            if required and required not in resolved:
                if required not in tests:
                    raise ValueError(f"Missing prerequisite in catalog: {required}")
                resolved.insert(0, required)
            index += 1
        return resolved


class EventStream:
    """Tail an NDJSON file and fan events out to WebSocket subscribers."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._watch_task: asyncio.Task[None] | None = None

    async def publish(self, event: dict[str, Any]) -> None:
        for queue in tuple(self._subscribers):
            await queue.put(event)

    async def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers.discard(queue)

    def watch(self, path: Path) -> None:
        if self._watch_task is not None:
            self._watch_task.cancel()
        self._watch_task = asyncio.create_task(self._tail(path))

    async def _tail(self, path: Path) -> None:
        offset = 0
        while True:
            if path.exists():
                if path.stat().st_size < offset:
                    offset = 0
                with path.open(encoding="utf-8") as stream:
                    stream.seek(offset)
                    for line in stream:
                        try:
                            await self.publish(json.loads(line))
                        except json.JSONDecodeError:
                            continue
                    offset = stream.tell()
            await asyncio.sleep(0.15)

    async def stop(self) -> None:
        if self._watch_task is not None:
            self._watch_task.cancel()
            await asyncio.gather(self._watch_task, return_exceptions=True)
            self._watch_task = None


class PytestRunner:
    """Own the single pytest subprocess and its event file."""

    def __init__(self, root: Path, catalog: WorkflowCatalog, events: EventStream) -> None:
        self.root = root
        self.catalog = catalog
        self.events = events
        self.process: asyncio.subprocess.Process | None = None
        self._guard = asyncio.Lock()
        self._completion_task: asyncio.Task[None] | None = None
        self._cancelled = False
        self.run_id: str | None = None

    @property
    def running(self) -> bool:
        return self.process is not None

    async def start(self, request: RunRequest) -> list[str]:
        async with self._guard:
            if self.running:
                raise RuntimeError("A test run is already active.")
            node_ids = await self.catalog.resolve(request.node_ids)
            if any("/calibration/" in node_id for node_id in node_ids) and not request.flex_ready:
                raise PermissionError("Confirm that the Flex is set up before running calibration tests.")

            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            self.run_id = uuid4().hex
            event_path = RESULTS_DIR / f"ui-events-{self.run_id}.ndjson"
            event_path.write_text("", encoding="utf-8")
            self._cancelled = False
            robot_name = request.robot_name.strip()
            protocol_name = request.protocol_name.strip()
            if not robot_name or not protocol_name:
                raise ValueError("Robot name and protocol name are required.")

            environment = os.environ.copy()
            environment["SKIP_FLEX_SETUP_PROMPT"] = "1"
            # UI suite: record failure, emit video path, continue to the next test (no page.pause).
            environment["E2E_NO_PAUSE"] = "1"
            environment["ROBOT_NAME"] = robot_name
            environment["PROTOCOL_NAME"] = protocol_name
            if request.headed:
                environment["HEADED"] = "1"
            else:
                environment.pop("HEADED", None)
            _upsert_env_keys({"ROBOT_NAME": robot_name, "PROTOCOL_NAME": protocol_name})
            command = [
                sys.executable,
                "-m",
                "pytest",
                *node_ids,
                "--robot-name",
                robot_name,
                "-p",
                "automation.ui_runner.event_plugin",
                f"--e2e-events={event_path}",
            ]
            self.events.watch(event_path)
            self.process = await asyncio.create_subprocess_exec(
                *command,
                cwd=self.root,
                env=environment,
                start_new_session=True,
            )
            await self.events.publish(
                {
                    "type": "runner_start",
                    "run_id": self.run_id,
                    "node_ids": node_ids,
                    "robot_name": robot_name,
                    "protocol_name": protocol_name,
                }
            )
            self._completion_task = asyncio.create_task(self._wait_for_completion())
            return node_ids

    async def _wait_for_completion(self) -> None:
        process = self.process
        if process is None:
            return
        return_code = await process.wait()
        await asyncio.sleep(0.25)
        async with self._guard:
            event_type = "run_cancelled" if self._cancelled else "runner_end"
            await self.events.publish(
                {
                    "type": event_type,
                    "run_id": self.run_id,
                    "exit_status": return_code,
                }
            )
            if self.process is process:
                self.process = None
                self.run_id = None

    async def cancel(self) -> bool:
        completion_task: asyncio.Task[None] | None
        cancelled = False
        async with self._guard:
            if self.process is None:
                return False
            if self.process.returncode is None:
                cancelled = True
                self._cancelled = True
                try:
                    os.killpg(self.process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                else:
                    try:
                        await asyncio.wait_for(self.process.wait(), timeout=10)
                    except TimeoutError:
                        os.killpg(self.process.pid, signal.SIGKILL)
                        await self.process.wait()
            completion_task = self._completion_task
        if completion_task is not None:
            await completion_task
        return cancelled


catalog = WorkflowCatalog(ROOT)
event_stream = EventStream()
runner = PytestRunner(ROOT, catalog, event_stream)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    del app
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    yield
    if runner.running:
        await runner.cancel()
    await event_stream.stop()


app = FastAPI(title="Opentrons E2E Workflow Runner", lifespan=lifespan)


@app.get("/api/defaults")
async def get_defaults() -> dict[str, str]:
    """Robot and protocol names for the run form (env / .env / built-in)."""
    return resolve_run_defaults()


@app.get("/api/catalog")
async def get_catalog(refresh: bool = False) -> dict[str, Any]:
    try:
        return await catalog.load(refresh=refresh)
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@app.get("/api/source")
async def get_source(path: str = Query(min_length=1), line: int | None = Query(default=None, ge=1)) -> dict[str, Any]:
    try:
        resolved = resolve_repo_path(path)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    content = resolved.read_text(encoding="utf-8")
    lines = content.splitlines()
    return {
        "path": resolved.relative_to(ROOT).as_posix(),
        "absolute_path": str(resolved),
        "line": line,
        "content": content,
        "line_count": len(lines),
    }


@app.post("/api/run", status_code=202)
async def start_run(request: RunRequest) -> dict[str, Any]:
    try:
        node_ids = await runner.start(request)
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"status": "started", "node_ids": node_ids}


@app.post("/api/cancel")
async def cancel_run() -> dict[str, bool]:
    return {"cancelled": await runner.cancel()}


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        async for event in event_stream.subscribe():
            await websocket.send_json(event)
    except WebSocketDisconnect:
        return


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/artifacts", StaticFiles(directory=ARTIFACTS_DIR, check_dir=False), name="artifacts")
app.mount("/test-results", StaticFiles(directory=RESULTS_DIR, check_dir=False), name="test-results")


def main() -> None:
    import uvicorn

    uvicorn.run("automation.ui_runner.server:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()

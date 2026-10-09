#!/usr/bin/env python3
"""Regenerate ``test_catalog.html`` from live tests and ``testing_workflows.md``.

Usage:
    uv run python scripts/generate_test_catalog.py
    make catalog
"""

from __future__ import annotations

import ast
import json
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_HTML = ROOT / "test_catalog.html"
RUNBOOK = ROOT / "testing_workflows.md"
MANIFEST_PLUGIN = "automation.ui_runner.collect_plugin"

# Keep in sync with automation.ui_runner.workflows.CATALOG_PATHS.
CATALOG_PATHS = ("tests/app", "tests/odd")

TOOLING_ROWS = [
    {
        "suite": "tooling/Regression_test_tooling",
        "file": ".cursor/skills/Regression_test_tooling/scripts/update_robot.py",
        "test": "update_robot.py (CLI)",
        "label": "Flex system update / downgrade (USB or network)",
        "group": "smoke_update",
        "section": "Update / Downgrade",
        "doc": (
            "Apply one or more ot3-system zips; waits for health between consecutive "
            "update→downgrade→upgrade."
        ),
        "cases": [
            {"id": "T70405", "name": "Update via USB"},
            {"id": "T70403", "name": "Update with Zip"},
            {"id": "T70407", "name": "Downgrade via Zip"},
            {"id": "C44434", "name": "Downgrade/upgrade"},
        ],
        "ids": ["T70405", "T70403", "T70407", "C44434"],
        "params": ["--usb", "--file", "--version", "network IP"],
        "skipped": False,
        "skip_reason": "",
        "in_runbook": True,
        "kind": "tooling",
    },
    {
        "suite": "tooling/Regression_test_tooling",
        "file": ".cursor/skills/Regression_test_tooling/scripts/update_robot_session.py",
        "test": "update_robot_session.py",
        "label": "Network update session (begin → upload → commit)",
        "group": "smoke_update",
        "section": "Update / Downgrade",
        "doc": "HTTP update API session helpers used by update_robot.py over the network.",
        "cases": [],
        "ids": [],
        "params": [],
        "skipped": False,
        "skip_reason": "",
        "in_runbook": True,
        "kind": "tooling",
    },
    {
        "suite": "tooling/Regression_test_tooling",
        "file": ".cursor/skills/Regression_test_tooling/scripts/update_robot_verifications.py",
        "test": "update_robot_verifications.py",
        "label": "Post-restart health / instruments / modules checks",
        "group": "smoke_update",
        "section": "Update / Downgrade",
        "doc": "Waits for /health, subsystem firmware idle, and stable Flex snapshot after update.",
        "cases": [],
        "ids": [],
        "params": [],
        "skipped": False,
        "skip_reason": "",
        "in_runbook": True,
        "kind": "tooling",
    },
    {
        "suite": "tooling/Regression_test_tooling",
        "file": ".cursor/skills/Regression_test_tooling/scripts/check_health.py",
        "test": "check_health.py",
        "label": "Robot health check (IP or USB)",
        "group": "smoke_update",
        "section": "Update / Downgrade",
        "doc": "GET /health (and optional update-server health) by IP or --usb.",
        "cases": [],
        "ids": [],
        "params": ["--usb", "IP"],
        "skipped": False,
        "skip_reason": "",
        "in_runbook": True,
        "kind": "tooling",
    },
]


def _suite_for(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    if rel.startswith("tests/app/"):
        parts = Path(rel).parts
        return f"app/{parts[2]}" if len(parts) > 3 else "app"
    if rel.startswith("tests/odd/"):
        return "odd"
    if rel.startswith("tests/compliance/"):
        return "compliance"
    if rel.startswith("tests/"):
        return "(root)"
    return Path(rel).parent.as_posix()


def _kind_for(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    if "abr_orchestration" in rel:
        return "abr"
    if "/calibration/" in rel:
        return "calibration"
    if "/device_cards/" in rel:
        return "device_cards"
    if "/nav/" in rel:
        return "nav"
    if "/odd/" in rel:
        return "odd"
    if "/compliance/" in rel:
        return "compliance"
    if path.name in {"test_ui_runner.py", "test_screencast_recorder.py"}:
        return "infra"
    return "other"


def _humanize(name: str) -> str:
    text = re.sub(r"^test_", "", name)
    text = text.replace("_", " ").strip()
    return text or name


def _docstring(node: ast.AST) -> str:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return ""
    body = ast.get_docstring(node) or ""
    return " ".join(body.strip().split())


def _skip_info(decorators: list[ast.expr]) -> tuple[bool, str]:
    for dec in decorators:
        call = dec if isinstance(dec, ast.Call) else None
        name = ""
        if isinstance(dec, ast.Attribute):
            name = dec.attr
        elif isinstance(dec, ast.Name):
            name = dec.id
        elif isinstance(call, ast.Call):
            func = call.func
            if isinstance(func, ast.Attribute):
                name = func.attr
            elif isinstance(func, ast.Name):
                name = func.id
        if name != "skip":
            continue
        reason = ""
        if call is not None:
            for kw in call.keywords:
                if kw.arg == "reason" and isinstance(kw.value, ast.Constant):
                    reason = str(kw.value.value)
            if not reason and call.args and isinstance(call.args[0], ast.Constant):
                reason = str(call.args[0].value)
        return True, reason
    return False, ""


def _ticket_ids(text: str) -> list[str]:
    return sorted(set(re.findall(r"\b(?:T|C)\d{4,6}\b", text or "")))


def _in_runbook(runbook: str, *, test: str, label: str, ids: list[str]) -> bool:
    if any(ticket in runbook for ticket in ids):
        return True
    if test and test in runbook:
        return True
    if label and len(label) > 8 and label in runbook:
        return True
    return False


def _collect_workflow_manifest() -> list[dict]:
    import subprocess
    import sys

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as handle:
        destination = Path(handle.name)
    command = [
        sys.executable,
        "-m",
        "pytest",
        *CATALOG_PATHS,
        "--collect-only",
        "-q",
        "-p",
        MANIFEST_PLUGIN,
        f"--e2e-manifest={destination}",
        "-o",
        "addopts=",
    ]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    if completed.returncode not in (0, 5) or not destination.exists():
        raise RuntimeError(
            f"pytest catalog collection failed ({completed.returncode}):\n"
            f"{completed.stdout}\n{completed.stderr}"
        )
    try:
        payload = json.loads(destination.read_text(encoding="utf-8"))
    finally:
        destination.unlink(missing_ok=True)
    return list(payload.get("tests") or [])


def _rows_from_manifest(manifest: list[dict], runbook: str) -> list[dict]:
    rows: list[dict] = []
    for entry in manifest:
        node_id = entry["node_id"]
        file_part, _, test_part = node_id.partition("::")
        path = ROOT / file_part
        cases = [
            {"id": case["id"], "name": case.get("title") or case.get("name") or ""}
            for case in entry.get("cases") or []
        ]
        ids = [case["id"] for case in cases]
        params: list[str] = []
        if "[" in test_part and test_part.endswith("]"):
            base, _, param = test_part.partition("[")
            test_name = base
            params = [param[:-1]]
        else:
            test_name = test_part
        doc = ""
        if path.is_file():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == test_name:
                    doc = _docstring(node)
                    break
        rows.append(
            {
                "suite": _suite_for(path),
                "file": file_part,
                "test": test_name,
                "label": entry.get("label") or _humanize(test_name),
                "group": entry.get("group") or "",
                "section": entry.get("section") or "",
                "doc": doc,
                "cases": cases,
                "ids": ids,
                "params": params,
                "skipped": not entry.get("implemented", True),
                "skip_reason": entry.get("skip_reason") or "",
                "in_runbook": _in_runbook(
                    runbook,
                    test=test_name,
                    label=entry.get("label") or "",
                    ids=ids,
                ),
                "kind": _kind_for(path),
            }
        )
    return rows


def _rows_from_other_tests(runbook: str, *, skip_files: set[str]) -> list[dict]:
    rows: list[dict] = []
    catalog_prefixes = tuple(f"{path}/" for path in CATALOG_PATHS)
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if rel in skip_files or rel.startswith(catalog_prefixes):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            skipped, reason = _skip_info(node.decorator_list)
            doc = _docstring(node)
            ids = _ticket_ids(doc)
            label = _humanize(node.name)
            rows.append(
                {
                    "suite": _suite_for(path),
                    "file": rel,
                    "test": node.name,
                    "label": label,
                    "group": "",
                    "section": "",
                    "doc": doc,
                    "cases": [{"id": ticket, "name": ticket} for ticket in ids],
                    "ids": ids,
                    "params": [],
                    "skipped": skipped,
                    "skip_reason": reason,
                    "in_runbook": _in_runbook(runbook, test=node.name, label=label, ids=ids),
                    "kind": _kind_for(path),
                }
            )
    return rows


def _write_catalog(rows: list[dict]) -> None:
    template = CATALOG_HTML.read_text(encoding="utf-8")
    match = re.search(r"const DATA = \[.*?\];\n", template, flags=re.S)
    if not match:
        raise RuntimeError(f"Could not find DATA assignment in {CATALOG_HTML}")
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    updated = template[: match.start()] + f"const DATA = {payload};\n" + template[match.end() :]
    CATALOG_HTML.write_text(updated, encoding="utf-8")


def main() -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8") if RUNBOOK.exists() else ""
    manifest = _collect_workflow_manifest()
    catalog_rows = _rows_from_manifest(manifest, runbook)
    skip_files = {row["file"] for row in catalog_rows}
    other_rows = _rows_from_other_tests(runbook, skip_files=skip_files)
    rows = catalog_rows + other_rows + TOOLING_ROWS
    _write_catalog(rows)
    print(f"Wrote {len(rows)} rows to {CATALOG_HTML.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

"""Pause until an operator types a value.

``make ui`` sets ``E2E_PROMPT_DIR``. The test emits a ``prompt`` event and
polls ``{dir}/{prompt_id}.json`` for the answer posted by the runner.
A headed terminal run asks on stdin instead.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from automation.app_helpers.test_progress import emit_event, safe_print

PROMPT_DIR_ENV = "E2E_PROMPT_DIR"


class OperatorPromptError(RuntimeError):
    """The operator prompt was not answered."""


def request_text(
    *,
    title: str,
    message: str,
    placeholder: str = "",
    timeout_s: float = 300,
) -> str:
    """Return the text the operator submits for this prompt."""
    prompt_dir = os.environ.get(PROMPT_DIR_ENV, "").strip()
    if not prompt_dir:
        return _request_from_stdin(title=title, message=message)
    return _request_from_runner(
        directory=Path(prompt_dir),
        title=title,
        message=message,
        placeholder=placeholder,
        timeout_s=timeout_s,
    )


def _request_from_stdin(*, title: str, message: str) -> str:
    safe_print(f"\n{title}\n{message}")
    try:
        value = input(f"{title}: ").strip()
    except EOFError as error:
        raise OperatorPromptError(
            "No terminal is attached. Run this test from make ui so the encryption key can be entered there."
        ) from error
    if not value:
        raise OperatorPromptError(f"{title} was left empty.")
    return value


def _request_from_runner(
    *,
    directory: Path,
    title: str,
    message: str,
    placeholder: str,
    timeout_s: float,
) -> str:
    prompt_id = uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=True)
    answer_path = directory / f"{prompt_id}.json"
    emit_event(
        {
            "type": "prompt",
            "prompt_id": prompt_id,
            "title": title,
            "message": message,
            "placeholder": placeholder,
        }
    )
    safe_print(f"  [wait] {title} — enter it in the workflow runner")
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if answer_path.is_file():
            value = _read_answer(answer_path)
            if value:
                return value
        time.sleep(0.25)
    raise OperatorPromptError(f"Timed out after {timeout_s:.0f}s waiting for {title} in the workflow runner.")


def _read_answer(path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("value", "")).strip()

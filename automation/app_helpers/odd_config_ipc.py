"""Watch ODD shell config writes over Electron IPC.

Automatically download updates, touchscreen sleep, and touchscreen brightness
are stored in the touchscreen ``config.json``. The renderer asks the shell to
write them with ``ipcRenderer.send('dispatch', ...)``. After the file write,
the shell sends ``config:VALUE_UPDATED`` back on that same channel.

The ODD preload exposes ``ipcRenderer`` on ``global.APP_SHELL_REMOTE`` because
context isolation is off. This helper listens from the CDP page, which is that
renderer.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from playwright.sync_api import Page

_START = """() => {
  const scopes = [globalThis]
  if (typeof global !== "undefined") scopes.push(global)
  if (typeof window !== "undefined") scopes.push(window)
  let remote = null
  for (const scope of scopes) {
    if (scope && scope.APP_SHELL_REMOTE && scope.APP_SHELL_REMOTE.ipcRenderer) {
      remote = scope.APP_SHELL_REMOTE
      break
    }
  }
  if (remote == null) {
    throw new Error(
      "APP_SHELL_REMOTE.ipcRenderer is missing. The ODD preload did not expose Electron IPC."
    )
  }
  if (window.__oddConfigIpcListener) {
    remote.ipcRenderer.removeListener("dispatch", window.__oddConfigIpcListener)
  }
  window.__oddConfigUpdates = []
  const listener = (_event, action) => {
    if (action && action.type === "config:VALUE_UPDATED" && action.payload) {
      window.__oddConfigUpdates.push({
        path: action.payload.path,
        value: action.payload.value,
      })
    }
  }
  window.__oddConfigIpcListener = listener
  remote.ipcRenderer.on("dispatch", listener)
}"""

_STOP = """() => {
  const scopes = [globalThis]
  if (typeof global !== "undefined") scopes.push(global)
  if (typeof window !== "undefined") scopes.push(window)
  let remote = null
  for (const scope of scopes) {
    if (scope && scope.APP_SHELL_REMOTE && scope.APP_SHELL_REMOTE.ipcRenderer) {
      remote = scope.APP_SHELL_REMOTE
      break
    }
  }
  if (remote != null && window.__oddConfigIpcListener) {
    remote.ipcRenderer.removeListener("dispatch", window.__oddConfigIpcListener)
  }
  window.__oddConfigIpcListener = null
  window.__oddConfigUpdates = []
}"""

_CLEAR = "() => { window.__oddConfigUpdates = [] }"

_HAS_PATH = """(path) => {
  if (!window.__oddConfigIpcListener) {
    throw new Error("ODD config IPC listener is not installed")
  }
  return (window.__oddConfigUpdates || []).some((item) => item.path === path)
}"""

_MATCHES = """(path) => (window.__oddConfigUpdates || []).filter((item) => item.path === path)"""


def start(page: Page) -> None:
    """Install one ``dispatch`` listener that records ``config:VALUE_UPDATED`` payloads."""
    page.evaluate(_START)


def stop(page: Page) -> None:
    """Remove the listener and drop recorded payloads."""
    page.evaluate(_STOP)


def clear(page: Page) -> None:
    """Drop recorded payloads without removing the listener."""
    page.evaluate(_CLEAR)


def wait_for_value(page: Page, path: str, *, timeout: float = 15_000) -> Any:
    """Return the latest ``config:VALUE_UPDATED`` value for ``path``."""
    page.wait_for_function(_HAS_PATH, arg=path, timeout=timeout)
    matches = page.evaluate(_MATCHES, path)
    if not matches:
        raise AssertionError(f"No config:VALUE_UPDATED for {path}")
    return matches[-1]["value"]


@contextmanager
def listen_for_config_updates(page: Page) -> Iterator[None]:
    """Record config IPC updates until the test leaves this block."""
    start(page)
    try:
        yield
    finally:
        stop(page)

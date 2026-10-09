"""Prepare File Manager downloads so E2E can click Download without OS dialogs.

Two pieces, same helper the suite already uses for log downloads:

1. Clear stable ``{robot}_logs.zip`` / calibration / run-record names under
   Downloads so Electron does not show a Replace sheet.
2. Inject ``destination`` into ``downloads:saveLogs`` (and sibling) IPC so
   app-shell skips ``dialog.showOpenDialog`` entirely — same contract as
   ``fs/__tests__/ipc.test.ts`` when destination is provided.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page

DEFAULT_DOWNLOADS_DIR = Path.home() / "Downloads"

_PATCH_SAVE_DIR = """(dir) => {
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
      "APP_SHELL_REMOTE.ipcRenderer is missing. Desktop preload did not expose Electron IPC."
    )
  }
  const ipc = remote.ipcRenderer
  const channels = new Set([
    "downloads:saveLogs",
    "downloads:saveFileFromBuffer",
    "downloads:saveFileFromUrl",
  ])
  ipc.__otSaveDir = dir
  window.__otSaveDirIntercepts = []
  // Always install our wrapper on the *current* invoke. A prior spy/helper may
  // have replaced ipc.invoke after an earlier prepare; re-wrap so destination
  // injection cannot be skipped.
  if (!ipc.__otSaveDirOriginal) {
    ipc.__otSaveDirOriginal = ipc.invoke.bind(ipc)
  }
  const original = ipc.__otSaveDirOriginal
  ipc.invoke = (channel, ...args) => {
    if (
      channels.has(channel) &&
      args.length > 0 &&
      args[0] &&
      typeof args[0] === "object" &&
      (args[0].destination == null || args[0].destination === "")
    ) {
      args[0] = Object.assign({}, args[0], { destination: ipc.__otSaveDir })
    }
    if (channels.has(channel)) {
      window.__otSaveDirIntercepts.push({
        channel,
        destination: args[0] && args[0].destination,
        name: args[0] && args[0].name,
      })
    }
    return original(channel, ...args)
  }
  ipc.__otSaveDirPatched = true
  return dir
}"""


def file_manager_download_names(robot_name: str) -> tuple[str, ...]:
    """Stable filenames File Manager writes for ``robot_name``."""
    return (
        f"{robot_name}_logs.zip",
        f"{robot_name}-calibration.json",
        f"{robot_name}-run-records.zip",
    )


def clear_download_collisions(
    *filenames: str,
    downloads_dir: Path | None = None,
) -> list[Path]:
    """Delete existing download targets so the next save won't prompt Replace.

    Returns the paths that were removed. Missing files are ignored.
    """
    root = downloads_dir if downloads_dir is not None else DEFAULT_DOWNLOADS_DIR
    removed: list[Path] = []
    for name in filenames:
        path = root / name
        if path.is_file():
            path.unlink()
            removed.append(path)
    return removed


def clear_file_manager_downloads(
    robot_name: str,
    *,
    downloads_dir: Path | None = None,
) -> list[Path]:
    """Clear all known File Manager download names for ``robot_name``."""
    return clear_download_collisions(
        *file_manager_download_names(robot_name),
        downloads_dir=downloads_dir,
    )


def prepare_file_manager_downloads(
    page: Page,
    robot_name: str,
    *,
    downloads_dir: Path | None = None,
) -> Path:
    """Clear collision files and route saves to ``downloads_dir`` (default ~/Downloads).

    Call before Download selected / Delete selected. No OS Save folder picker.
    """
    target = (downloads_dir if downloads_dir is not None else DEFAULT_DOWNLOADS_DIR).expanduser()
    target = target.resolve()
    target.mkdir(parents=True, exist_ok=True)
    clear_file_manager_downloads(robot_name, downloads_dir=target)
    page.evaluate(_PATCH_SAVE_DIR, str(target))
    return target

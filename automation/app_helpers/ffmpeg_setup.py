"""Find the ffmpeg CLI, including a winget install the current process cannot see."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

_WINGET_INSTALL = [
    "winget",
    "install",
    "--id",
    "Gyan.FFmpeg",
    "-e",
    "--source",
    "winget",
    "--accept-source-agreements",
    "--accept-package-agreements",
    "--disable-interactivity",
]


def tool_executable(name: str) -> str | None:
    """Return ``ffmpeg`` or ``ffprobe``, searching the registry PATH when the process PATH is stale."""
    found = shutil.which(name)
    if found:
        return found
    filename = f"{name}.exe" if os.name == "nt" else name
    for directory in _registry_path_dirs():
        candidate = directory / filename
        if candidate.is_file():
            _prepend_path(directory)
            return str(candidate)
    return None


def ensure_ffmpeg() -> str:
    """Make ``ffmpeg`` available to this process and to child test runs.

    A winget install updates the user PATH in the registry, which already-running
    apps (including Cursor) do not inherit. When the binary is still absent, install
    it the same way ``make setup`` does.
    """
    found = tool_executable("ffmpeg")
    if found is None:
        print("ffmpeg: not found; installing", flush=True)
        _install_ffmpeg()
        found = tool_executable("ffmpeg")
    if found is None:
        raise SystemExit("ffmpeg is required for test video encoding. Install it, then restart the runner.")
    tool_executable("ffprobe")
    print(f"ffmpeg: {found}", flush=True)
    return found


def _install_ffmpeg() -> None:
    if os.name == "nt" and shutil.which("winget"):
        print("ffmpeg: installing with winget", flush=True)
        subprocess.run(_WINGET_INSTALL, check=False)
        return
    if shutil.which("brew"):
        print("ffmpeg: installing with Homebrew", flush=True)
        subprocess.run(["brew", "install", "ffmpeg"], check=False)
        return
    if shutil.which("apt-get"):
        print("ffmpeg: installing with apt", flush=True)
        subprocess.run(["sudo", "apt-get", "update"], check=False)
        subprocess.run(["sudo", "apt-get", "install", "-y", "ffmpeg"], check=False)
        return
    print(
        "ffmpeg is required for test video encoding. Install it, then restart the runner.",
        file=sys.stderr,
        flush=True,
    )


def _registry_path_dirs() -> list[Path]:
    if os.name != "nt":
        return []
    import winreg

    locations = (
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
    )
    directories: list[Path] = []
    for hive, subkey in locations:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                raw, _ = winreg.QueryValueEx(key, "Path")
        except OSError:
            continue
        for entry in os.path.expandvars(str(raw)).split(";"):
            cleaned = entry.strip().strip('"')
            if cleaned:
                directories.append(Path(cleaned))
    return directories


def _prepend_path(directory: Path) -> None:
    entry = str(directory)
    parts = [part for part in os.environ.get("PATH", "").split(os.pathsep) if part]
    if entry not in parts:
        os.environ["PATH"] = os.pathsep.join([entry, *parts])

"""ffmpeg lookup must see a winget install that is not on the process PATH."""

from __future__ import annotations

import os
from pathlib import Path

from automation.app_helpers.ffmpeg_setup import ensure_ffmpeg, tool_executable


def test_tool_executable_reads_registry_path(monkeypatch, tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    executable = bin_dir / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    executable.write_bytes(b"")
    monkeypatch.setattr("automation.app_helpers.ffmpeg_setup.shutil.which", lambda _name: None)
    monkeypatch.setattr(
        "automation.app_helpers.ffmpeg_setup._registry_path_dirs",
        lambda: [bin_dir],
    )
    monkeypatch.setenv("PATH", "")

    found = tool_executable("ffmpeg")

    assert found == str(executable)
    assert str(bin_dir) in os.environ["PATH"].split(os.pathsep)


def test_ensure_ffmpeg_installs_when_absent(monkeypatch) -> None:
    installed: list[bool] = []
    ffmpeg_lookups = {"count": 0}

    def _lookup(name: str) -> str | None:
        if name == "ffmpeg":
            ffmpeg_lookups["count"] += 1
            if ffmpeg_lookups["count"] == 1:
                return None
            return r"C:\ffmpeg\bin\ffmpeg.exe"
        return r"C:\ffmpeg\bin\ffprobe.exe"

    monkeypatch.setattr("automation.app_helpers.ffmpeg_setup.tool_executable", _lookup)
    monkeypatch.setattr(
        "automation.app_helpers.ffmpeg_setup._install_ffmpeg",
        lambda: installed.append(True),
    )

    assert ensure_ffmpeg() == r"C:\ffmpeg\bin\ffmpeg.exe"
    assert installed == [True]


def test_ensure_ffmpeg_skips_install_when_present(monkeypatch) -> None:
    monkeypatch.setattr(
        "automation.app_helpers.ffmpeg_setup.tool_executable",
        lambda _name: r"C:\ffmpeg\bin\ffmpeg.exe",
    )

    def _fail_install() -> None:
        raise AssertionError("install should not run")

    monkeypatch.setattr("automation.app_helpers.ffmpeg_setup._install_ffmpeg", _fail_install)

    assert ensure_ffmpeg() == r"C:\ffmpeg\bin\ffmpeg.exe"

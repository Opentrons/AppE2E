"""Video duration stays aligned with the time a workflow actually takes."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from automation.app_helpers.screencast_recorder import (
    CDP_HTTP_ATTR,
    ScreencastRecorder,
    encode_timestamped_jpegs,
    probe_duration_seconds,
)


def _jpeg(path: Path, color: str) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=320x240",
            "-frames:v",
            "1",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def test_sparse_frames_hold_for_the_whole_workflow(tmp_path: Path) -> None:
    """A handful of paints must still produce a video as long as the test."""
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    start = 1_000.0
    frames: list[tuple[float, Path]] = []
    for index, color in enumerate(("red", "blue", "green")):
        path = frames_dir / f"frame_{index:06d}.jpg"
        _jpeg(path, color)
        frames.append((start + 0.4 + index, path))

    saved = encode_timestamped_jpegs(frames, tmp_path / "workflow.mp4", start=start, end=start + 3.0)
    assert saved is not None
    duration = probe_duration_seconds(saved)
    assert duration is not None
    assert duration == pytest.approx(3.0, abs=0.35)

    codec = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(saved),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert codec.stdout.strip() == "h264"


def test_live_cdp_video_matches_wall_clock(tmp_path: Path) -> None:
    """Polling the page keeps the recording going while the UI sits still."""
    import socket

    from playwright.sync_api import sync_playwright

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    video_path = tmp_path / "live.mp4"
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(
                headless=True,
                args=[f"--remote-debugging-port={port}"],
            )
        except Exception as error:
            pytest.skip(f"Chromium is not available: {error}")
        try:
            page = browser.new_page()
            page.set_content("<title>workflow</title><body style='background:#222'>workflow</body>")
            setattr(browser, CDP_HTTP_ATTR, f"http://127.0.0.1:{port}")
            recorder = ScreencastRecorder(page, video_path, interval_s=0.25)
            recorder.start()
            for color in ("#c0392b", "#27ae60", "#2980b9", "#f1c40f", "#ecf0f1"):
                page.evaluate("(color) => { document.body.style.background = color }", color)
                page.wait_for_timeout(500)
            saved = recorder.stop()
        finally:
            browser.close()

    assert saved is not None
    assert saved.exists()
    duration = probe_duration_seconds(saved)
    assert duration is not None
    assert duration >= 2.0

    early = tmp_path / "early.png"
    late = tmp_path / "late.png"
    for stamp, dest in (("0.2", early), ("2.0", late)):
        subprocess.run(
            ["ffmpeg", "-y", "-ss", stamp, "-i", str(saved), "-frames:v", "1", str(dest)],
            check=True,
            capture_output=True,
        )
    assert early.read_bytes() != late.read_bytes()

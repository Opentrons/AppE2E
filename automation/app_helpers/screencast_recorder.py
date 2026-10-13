"""Wall-clock video capture for headed Electron and ODD tests.

Chromium's ``Page.startScreencast`` only emits a frame when pixels change, and
encoding those sparse frames at a fixed rate turned a multi-second workflow
into a fraction of a second. Playback also stalled when acks were sent on
Playwright's sync CDP session.

This recorder polls ``Page.captureScreenshot`` on its own debugger websocket
and stamps each frame with the time it was taken, so the encoded video lasts
as long as the test.
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page

from automation.app_helpers.ffmpeg_setup import tool_executable

# Stashed on the Playwright Browser by ``open_app.connect_playwright``.
CDP_HTTP_ATTR = "_e2e_cdp_http"

# Four frames a second keeps short assertion tests from collapsing to a single flash.
_CAPTURE_INTERVAL_S = 0.25
_JPEG_QUALITY = 55
_MAX_CDP_MESSAGE_BYTES = 32 * 1024 * 1024
# Sub-second tests still produce a playable clip that holds the final screen.
_MIN_VIDEO_DURATION_S = 2.0


class ScreencastRecorder:
    """Record ``page`` to an h264 ``.mp4`` whose duration matches the test."""

    def __init__(self, page: Page, output_path: Path, *, interval_s: float = _CAPTURE_INTERVAL_S) -> None:
        """Store the page to record and the destination ``.mp4`` path."""
        self.page = page
        self.output_path = output_path
        self._interval_s = interval_s
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._frames: list[tuple[float, Path]] = []
        self._lock = threading.Lock()
        self._frames_dir: Path | None = None
        self._started = 0.0
        self._thread_error: str | None = None

    def start(self) -> None:
        """Begin capturing frames on a background thread."""
        websocket_url = page_websocket_url(self.page)
        self._frames = []
        self._thread_error = None
        self._stop.clear()
        self._started = time.monotonic()
        self._frames_dir = Path(tempfile.mkdtemp(prefix="screencast_"))
        self._thread = threading.Thread(
            target=self._capture_loop,
            args=(websocket_url, self._frames_dir),
            name="screencast-capture",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> Path | None:
        """Stop capture and encode an mp4 that lasts as long as the recording."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=15)
            self._thread = None
        ended = time.monotonic()
        with self._lock:
            frames = list(self._frames)
        frames_dir = self._frames_dir
        self._frames_dir = None
        try:
            if self._thread_error and not frames:
                print(f"\n⚠️  Video capture failed: {self._thread_error}")
                return None
            if self._thread_error:
                print(f"\n⚠️  Video capture stopped early: {self._thread_error}")
            if not frames:
                print("\n⚠️  Video capture collected no frames")
                return None
            saved = encode_timestamped_jpegs(
                frames,
                self.output_path,
                start=self._started,
                end=ended,
                min_duration_s=_MIN_VIDEO_DURATION_S,
            )
            if saved is None:
                return None
            elapsed = max(0.0, ended - self._started)
            playback = probe_duration_seconds(saved) or elapsed
            print(f"\n📹 {saved.name} — {playback:.1f}s playback ({elapsed:.1f}s captured, {len(frames)} frames)")
            return saved
        finally:
            if frames_dir is not None:
                shutil.rmtree(frames_dir, ignore_errors=True)

    def _capture_loop(self, websocket_url: str, frames_dir: Path) -> None:
        """Poll screenshots until ``stop`` is called."""
        try:
            from websockets.sync.client import connect
        except ImportError:
            self._thread_error = "websockets is not installed"
            return

        index = 0
        speed_opt = True
        try:
            with connect(
                websocket_url,
                max_size=_MAX_CDP_MESSAGE_BYTES,
                compression=None,
                proxy=None,
                open_timeout=10,
                close_timeout=2,
            ) as websocket:
                while True:
                    began = time.monotonic()
                    params: dict[str, object] = {
                        "format": "jpeg",
                        "quality": _JPEG_QUALITY,
                        "fromSurface": True,
                        "captureBeyondViewport": False,
                    }
                    if speed_opt:
                        params["optimizeForSpeed"] = True
                    try:
                        result = _cdp_call(websocket, "Page.captureScreenshot", params)
                    except (RuntimeError, TimeoutError) as error:
                        if speed_opt and not self._stop.is_set():
                            speed_opt = False
                            continue
                        self._thread_error = str(error)
                        return
                    data = result.get("data")
                    if isinstance(data, str) and data:
                        frame_path = frames_dir / f"frame_{index:06d}.jpg"
                        frame_path.write_bytes(base64.b64decode(data))
                        with self._lock:
                            self._frames.append((time.monotonic(), frame_path))
                        index += 1
                    if self._stop.is_set():
                        # Frame above is the end-state snapshot for sub-interval tests.
                        return
                    remaining = self._interval_s - (time.monotonic() - began)
                    if remaining > 0 and self._stop.wait(remaining):
                        # Wake for a final capture after stop() is called mid-interval.
                        continue
        except Exception as error:
            self._thread_error = str(error)


def page_websocket_url(page: Page) -> str:
    """Return the DevTools websocket for this page's CDP target."""
    browser = page.context.browser
    cdp_http = getattr(browser, CDP_HTTP_ATTR, None) if browser is not None else None
    if not isinstance(cdp_http, str) or not cdp_http:
        raise RuntimeError("Browser has no CDP HTTP endpoint. Connect with open_app.connect_playwright.")
    target_id = _page_target_id(page)
    return _websocket_for_target(cdp_http.rstrip("/"), target_id=target_id, page_url=page.url)


def encode_timestamped_jpegs(
    frames: list[tuple[float, Path]],
    video_path: Path,
    *,
    start: float,
    end: float,
    min_duration_s: float = 0.0,
) -> Path | None:
    """Encode JPEG frames so each one stays on screen for the time it was visible."""
    if not frames:
        return None
    video_path.parent.mkdir(parents=True, exist_ok=True)
    origin = min(start, frames[0][0])
    finish = max(end, frames[-1][0] + 0.05)
    if min_duration_s > 0:
        finish = max(finish, origin + min_duration_s)
    concat_path = video_path.with_suffix(".ffconcat.txt")
    lines = ["ffconcat version 1.0"]
    for index, (timestamp, frame_path) in enumerate(frames):
        if index == 0:
            duration = (frames[1][0] if len(frames) > 1 else finish) - origin
        elif index == len(frames) - 1:
            duration = finish - timestamp
        else:
            duration = frames[index + 1][0] - timestamp
        duration = max(0.04, duration)
        lines.append(f"file '{_ffconcat_quote(frame_path)}'")
        lines.append(f"duration {duration:.3f}")
    lines.append(f"file '{_ffconcat_quote(frames[-1][1])}'")
    concat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        return _run_ffmpeg(
            video_path,
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_path),
                "-vf",
                "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "28",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-an",
            ],
        )
    finally:
        concat_path.unlink(missing_ok=True)


def concat_mp4s(parts: list[Path], video_path: Path, *, keep_parts: bool = False) -> Path | None:
    """Join mp4 segments into one file, re-encoding if stream copy fails.

    When ``keep_parts`` is false (default), successful joins delete the input
    segments — used for per-test workflow pieces. Suite concatenations pass
    ``keep_parts=True`` so individual test videos remain on disk.
    """
    existing = [path for path in parts if path.exists()]
    if not existing:
        return None
    if len(existing) == 1:
        return existing[0]
    video_path.parent.mkdir(parents=True, exist_ok=True)
    concat_path = video_path.with_suffix(".ffconcat.txt")
    lines = ["ffconcat version 1.0"]
    for part in existing:
        lines.append(f"file '{_ffconcat_quote(part)}'")
    concat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        saved = _run_ffmpeg(video_path, ["-f", "concat", "-safe", "0", "-i", str(concat_path), "-c", "copy"])
        if saved is None:
            saved = _run_ffmpeg(
                video_path,
                [
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_path),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "28",
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    "-an",
                ],
            )
        if saved is not None and not keep_parts:
            for part in existing:
                if part != saved:
                    part.unlink(missing_ok=True)
        return saved
    finally:
        concat_path.unlink(missing_ok=True)


def probe_duration_seconds(video_path: Path) -> float | None:
    """Return the container duration, or None when ffprobe cannot read it."""
    ffprobe = tool_executable("ffprobe")
    if ffprobe is None:
        return None
    try:
        completed = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    try:
        return float(completed.stdout.strip())
    except ValueError:
        return None


def _page_target_id(page: Page) -> str | None:
    session = page.context.new_cdp_session(page)
    try:
        info = session.send("Target.getTargetInfo")
    except Exception:
        return None
    finally:
        try:
            session.detach()
        except Exception:
            pass
    target = info.get("targetInfo") if isinstance(info, dict) else None
    if not isinstance(target, dict):
        return None
    target_id = target.get("targetId")
    return str(target_id) if target_id else None


def _websocket_for_target(cdp_http: str, *, target_id: str | None, page_url: str) -> str:
    with urllib.request.urlopen(f"{cdp_http}/json/list", timeout=5) as response:
        targets = json.load(response)
    pages = [
        target
        for target in targets
        if isinstance(target, dict) and target.get("type") == "page" and target.get("webSocketDebuggerUrl")
    ]
    if target_id is not None:
        for target in pages:
            if target.get("id") == target_id:
                return str(target["webSocketDebuggerUrl"])
    for target in pages:
        if target.get("url") == page_url:
            return str(target["webSocketDebuggerUrl"])
    if len(pages) == 1:
        return str(pages[0]["webSocketDebuggerUrl"])
    raise RuntimeError(f"No CDP page websocket for {page_url!r} at {cdp_http}")


def _cdp_call(websocket: object, method: str, params: dict[str, object], *, timeout: float = 8) -> dict:
    call_id = getattr(websocket, "_e2e_cdp_id", 0) + 1
    setattr(websocket, "_e2e_cdp_id", call_id)
    send = getattr(websocket, "send")
    recv = getattr(websocket, "recv")
    send(json.dumps({"id": call_id, "method": method, "params": params}))
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"{method} timed out")
        raw = recv(timeout=remaining)
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        message = json.loads(raw)
        if message.get("id") != call_id:
            continue
        if "error" in message:
            raise RuntimeError(f"{method} failed: {message['error']}")
        result = message.get("result")
        return result if isinstance(result, dict) else {}


def _ffconcat_quote(path: Path) -> str:
    return str(path.resolve()).replace("'", r"'\''")


def _run_ffmpeg(video_path: Path, args: list[str]) -> Path | None:
    ffmpeg = tool_executable("ffmpeg")
    if ffmpeg is None:
        print("\n⚠️  ffmpeg is not installed; video was not encoded")
        return None
    try:
        subprocess.run(
            [ffmpeg, "-y", *args, str(video_path)],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or b"").decode("utf-8", errors="replace")[-600:]
        print(f"\n⚠️  ffmpeg failed for {video_path.name}: {detail}")
        return None
    if not video_path.exists() or video_path.stat().st_size == 0:
        return None
    return video_path

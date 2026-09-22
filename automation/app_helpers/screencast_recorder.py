"""CDP screencast capture for headed Electron regression tests."""

from __future__ import annotations

import base64
import shutil
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import CDPSession, Page

# Match Playwright tracing's ballpark size. Full-res Electron frames (e.g. 2048x1536)
# are too large for reliable CDP screencast acks — Chrome stops sending after a few.
_SCREENCAST_MAX_WIDTH = 1280
_SCREENCAST_MAX_HEIGHT = 720
_SCREENCAST_QUALITY = 60
# Encode assuming ~10 fps; real capture rate varies with paints / ack latency.
_ENCODE_FRAMERATE = "10"


class ScreencastRecorder:
    """Record the Electron app page via CDP ``Page.startScreencast``.

    Must be the only active ``Page.startScreencast`` client on the page. Playwright
    tracing with ``screenshots=True`` also starts a screencast and will starve or
    replace this recorder — disable tracing screenshots while this is running.
    """

    def __init__(self, page: Page, output_path: Path) -> None:
        """Store the page to record and the destination ``.webm`` path."""
        self.page = page
        self.output_path = output_path
        self._cdp: CDPSession | None = None
        self._frames: list[bytes] = []

    def start(self) -> None:
        """Begin collecting JPEG screencast frames from the page."""
        self._frames = []
        self._cdp = self.page.context.new_cdp_session(self.page)
        self._cdp.on("Page.screencastFrame", self._on_screencast_frame)
        self._cdp.send(
            "Page.startScreencast",
            {
                "format": "jpeg",
                "quality": _SCREENCAST_QUALITY,
                "everyNthFrame": 1,
                "maxWidth": _SCREENCAST_MAX_WIDTH,
                "maxHeight": _SCREENCAST_MAX_HEIGHT,
            },
        )

    def _on_screencast_frame(self, params: dict) -> None:
        """Append a frame and acknowledge it so the next frame is delivered."""
        if self._cdp is None:
            return
        try:
            self._frames.append(base64.b64decode(params["data"]))
            self._cdp.send("Page.screencastFrameAck", {"sessionId": params["sessionId"]})
        except Exception:
            # A failed ack permanently stalls Chromium screencast; drop this frame
            # and hope a later paint delivers another with a fresh session id.
            pass

    def stop(self) -> Path | None:
        """Stop screencast and encode collected frames to ``output_path`` when possible."""
        if self._cdp is not None:
            try:
                self._cdp.send("Page.stopScreencast")
            except Exception:
                pass
            try:
                self._cdp.detach()
            except Exception:
                pass
            self._cdp = None

        if not self._frames:
            return None
        return encode_jpeg_frames_to_webm(self._frames, self.output_path)


def encode_jpeg_frames_to_webm(frames: list[bytes], video_path: Path) -> Path | None:
    """Write JPEG frames to a temp dir and encode them with ffmpeg."""
    video_path.parent.mkdir(parents=True, exist_ok=True)
    frames_dir = Path(tempfile.mkdtemp(prefix="screencast_"))
    try:
        for index, frame in enumerate(frames):
            (frames_dir / f"frame_{index:06d}.jpg").write_bytes(frame)
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-framerate",
                    _ENCODE_FRAMERATE,
                    "-i",
                    str(frames_dir / "frame_%06d.jpg"),
                    "-pix_fmt",
                    "yuv420p",
                    str(video_path),
                ],
                check=True,
                capture_output=True,
            )
            return video_path
        except (FileNotFoundError, subprocess.CalledProcessError):
            return None
    finally:
        shutil.rmtree(frames_dir, ignore_errors=True)

"""Connect to a robot over USB or Wi-Fi for app E2E test preflight checks."""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Optional

import httpx

from automation.app_helpers.robot_usb import find_opentrons_usb_port, http_get_over_serial

ROBOT_PORT = 31950
TIMEOUT = 10.0
DEFAULT_ROBOT_IP = "10.14.19.194"
# Factory reset / robot restart can take a long time on Flex hardware.
DEVICE_RESET_READY_TIMEOUT_S = 1_200.0
DEVICE_RESET_DOWNTIME_WAIT_S = 90.0
DEVICE_RESET_POLL_INTERVAL_S = 5.0


def resolve_robot_ip(*, cli_ip: str | None = None) -> str:
    """Resolve robot IP: ``--robot-ip`` > ``ROBOT_IP`` env > ``DEFAULT_ROBOT_IP``.

    Any routable address works (lab Wi-Fi, USB gadget ``169.254.x.x``, etc.).
    """
    for candidate in (
        (cli_ip or "").strip(),
        os.environ.get("ROBOT_IP", "").strip(),
        DEFAULT_ROBOT_IP,
    ):
        if candidate:
            return candidate
    return DEFAULT_ROBOT_IP


class RobotConnection:
    """Callable stand-in for a robot IP address."""

    def __init__(self, *, usb_port: Optional[str] = None, ip: Optional[str] = None) -> None:
        """Store USB serial port or network IP used for robot-server requests."""
        self.usb_port = usb_port
        self.ip = ip

    @property
    def over_usb(self) -> bool:
        """Return True when requests should go over the USB serial port."""
        return self.usb_port is not None

    def __call__(self, path: str) -> dict[str, Any]:
        """GET a robot-server path and return JSON (e.g. connection('/health'))."""
        if self.over_usb:
            assert self.usb_port is not None
            status, body = http_get_over_serial(self.usb_port, path, TIMEOUT)
        else:
            url = f"http://{self.ip}:{ROBOT_PORT}{path}"
            with httpx.Client(headers={"Opentrons-Version": "*"}, timeout=TIMEOUT) as client:
                resp = client.get(url)
                resp.raise_for_status()
                return resp.json()

        if status != 200:
            raise RuntimeError(f"GET {path} failed: HTTP {status}\n{body.decode('utf-8', errors='replace')}")
        return json.loads(body.decode("utf-8"))

    def _refresh_usb_port(self) -> bool:
        """Re-discover the Opentrons USB gadget after a reboot. Return True if found."""
        if not self.over_usb:
            return True
        port = find_opentrons_usb_port()
        if port is None:
            return False
        self.usb_port = port
        return True

    def wait_until_healthy(
        self,
        *,
        timeout_s: float = DEVICE_RESET_READY_TIMEOUT_S,
        poll_interval_s: float = DEVICE_RESET_POLL_INTERVAL_S,
    ) -> None:
        """Poll ``/health`` until the robot responds."""
        deadline = time.time() + timeout_s
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                if not self._refresh_usb_port():
                    time.sleep(poll_interval_s)
                    continue
                self("/health")
                return
            except Exception as exc:
                last_error = exc
                time.sleep(poll_interval_s)
        raise TimeoutError(
            f"Robot /health not ready after {timeout_s:.0f}s" + (f" (last error: {last_error})" if last_error else "")
        )

    def wait_for_ready_after_reset(
        self,
        *,
        timeout_s: float = DEVICE_RESET_READY_TIMEOUT_S,
        downtime_wait_s: float = DEVICE_RESET_DOWNTIME_WAIT_S,
        poll_interval_s: float = DEVICE_RESET_POLL_INTERVAL_S,
    ) -> None:
        """Wait for restart downtime (if any), then for ``/health`` to recover."""
        deadline = time.time() + timeout_s
        down_deadline = time.time() + downtime_wait_s
        while time.time() < down_deadline:
            try:
                if not self._refresh_usb_port():
                    break
                self("/health")
                time.sleep(min(poll_interval_s, 2.0))
            except Exception:
                break
        remaining = max(deadline - time.time(), poll_interval_s)
        self.wait_until_healthy(timeout_s=remaining, poll_interval_s=poll_interval_s)


def connect_robot(default_ip: Optional[str] = None) -> RobotConnection:
    """USB first; otherwise connect over Wi-Fi. Returns a callable connection."""
    usb_port = find_opentrons_usb_port()
    if usb_port is not None:
        connection = RobotConnection(usb_port=usb_port)
        connection("/health")
        print(f"Connected over USB ({usb_port})")
        return connection

    ip = resolve_robot_ip(cli_ip=default_ip)
    connection = RobotConnection(ip=ip)
    connection("/health")
    print(f"Connected over network ({ip}:{ROBOT_PORT})")
    return connection


def main() -> int:
    """CLI entry point: connect over USB or Wi-Fi and print status."""
    cli_ip = sys.argv[1].strip() if len(sys.argv) > 1 else None
    try:
        connect_robot(default_ip=cli_ip)
    except Exception as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
# /health alone is not enough — app discovery / menus need settle time.
DEVICE_RESET_SETTLE_S = 120.0


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
    """Callable stand-in for a robot over USB serial and/or Wi-Fi IP."""

    def __init__(self, *, usb_port: Optional[str] = None, ip: Optional[str] = None) -> None:
        """Store USB serial port and/or network IP used for robot-server requests."""
        self.usb_port = usb_port
        self.ip = ip

    @property
    def over_usb(self) -> bool:
        """Return True when the preferred request path is USB serial."""
        return self.usb_port is not None and self.ip is None

    def __call__(self, path: str) -> dict[str, Any]:
        """GET a robot-server path and return JSON (e.g. connection('/health'))."""
        return self._get(path)

    def _get_over_usb(self, path: str, port: str) -> dict[str, Any]:
        """GET ``path`` over the Opentrons USB serial gadget."""
        status, body = http_get_over_serial(port, path, TIMEOUT)
        if status != 200:
            raise RuntimeError(f"GET {path} via USB failed: HTTP {status}\n{body.decode('utf-8', errors='replace')}")
        return json.loads(body.decode("utf-8"))

    def _get_over_wifi(self, path: str, ip: str) -> dict[str, Any]:
        """GET ``path`` over Wi-Fi / Ethernet to ``ip:31950``."""
        url = f"http://{ip}:{ROBOT_PORT}{path}"
        with httpx.Client(headers={"Opentrons-Version": "*"}, timeout=TIMEOUT) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()

    def _get(self, path: str) -> dict[str, Any]:
        """GET via the active transport (USB preferred when both are set)."""
        if self.usb_port is not None:
            try:
                return self._get_over_usb(path, self.usb_port)
            except Exception:
                if self.ip is None:
                    raise
        if self.ip is not None:
            return self._get_over_wifi(path, self.ip)
        raise RuntimeError("RobotConnection has neither usb_port nor ip")

    def _network_ip(self) -> str | None:
        """Return a Wi-Fi/Ethernet IP to probe, if one is configured."""
        if self.ip:
            return self.ip
        # Prefer an explicit env/CLI IP over the lab default when we started on USB.
        for candidate in (
            os.environ.get("ROBOT_IP", "").strip(),
        ):
            if candidate:
                return candidate
        return None

    def _probe_health(self) -> dict[str, Any]:
        """GET ``/health`` via USB and/or Wi-Fi; adopt whichever transport succeeds.

        After device reset the original path may stay down (Wi-Fi wiped, USB
        gadget renumbered). Probe both so recovery works either way.
        """
        errors: list[str] = []

        # USB first when we already use it or a gadget is plugged in now.
        port = find_opentrons_usb_port()
        if port is not None:
            try:
                payload = self._get_over_usb("/health", port)
                self.usb_port = port
                return payload
            except Exception as exc:
                errors.append(f"usb:{port}:{exc}")

        ip = self._network_ip()
        if ip is not None:
            try:
                payload = self._get_over_wifi("/health", ip)
                self.ip = ip
                return payload
            except Exception as exc:
                errors.append(f"wifi:{ip}:{exc}")

        detail = "; ".join(errors) if errors else "no USB gadget and no ROBOT_IP"
        raise RuntimeError(f"/health probe failed ({detail})")

    def wait_until_healthy(
        self,
        *,
        timeout_s: float = DEVICE_RESET_READY_TIMEOUT_S,
        poll_interval_s: float = DEVICE_RESET_POLL_INTERVAL_S,
    ) -> dict[str, Any]:
        """Poll ``/health`` over USB and/or Wi-Fi until the robot responds.

        Returns the successful ``/health`` JSON payload.
        """
        deadline = time.time() + timeout_s
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                return self._probe_health()
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
        settle_s: float = DEVICE_RESET_SETTLE_S,
    ) -> dict[str, Any]:
        """Wait for restart downtime, ``/health`` on Wi-Fi or USB, then settle.

        Works for both transports: probes USB serial (with port rediscovery) and
        the configured Wi-Fi IP each poll. ``settle_s`` covers app-side
        rediscovery after the API is back (default 2 minutes).

        Returns the ``/health`` payload from the first successful post-reset probe.
        """
        deadline = time.time() + timeout_s
        down_deadline = time.time() + downtime_wait_s
        while time.time() < down_deadline:
            try:
                self._probe_health()
                time.sleep(min(poll_interval_s, 2.0))
            except Exception:
                break
        remaining = max(deadline - time.time(), poll_interval_s)
        health = self.wait_until_healthy(timeout_s=remaining, poll_interval_s=poll_interval_s)
        if settle_s > 0:
            time.sleep(settle_s)
        return health


def _explicit_robot_ip(*, cli_ip: str | None = None) -> str | None:
    """Return a caller-configured robot IP, or None (do not fall back to default)."""
    for candidate in ((cli_ip or "").strip(), os.environ.get("ROBOT_IP", "").strip()):
        if candidate:
            return candidate
    return None


def connect_robot(default_ip: Optional[str] = None) -> RobotConnection:
    """USB first; otherwise connect over Wi-Fi. Returns a callable connection.

    When USB is present and ``ROBOT_IP`` / ``cli_ip`` is set, both are kept so
    post-reset health waits can fall back either way.
    """
    explicit_ip = _explicit_robot_ip(cli_ip=default_ip)
    usb_port = find_opentrons_usb_port()
    if usb_port is not None:
        connection = RobotConnection(usb_port=usb_port, ip=explicit_ip)
        connection("/health")
        via = f"USB ({usb_port})" + (f", Wi-Fi fallback {explicit_ip}" if explicit_ip else "")
        print(f"Connected over {via}")
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

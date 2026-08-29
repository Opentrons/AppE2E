"""Parse and compare Opentrons desktop app software versions."""

from __future__ import annotations

import re

from packaging.version import InvalidVersion, Version

# Device Details RoundTabs (Hardware / Deck Configuration / Run History) ship after 9.1.2.
DEVICE_DETAILS_TABS_AFTER = Version("9.1.2")

_VERSION_TOKEN = re.compile(
    r"v?(?P<ver>\d+(?:\.\d+){0,2}(?:[-._]?(?:a|b|rc|alpha|beta|dev|post)\.?\d*)*)",
    re.IGNORECASE,
)


def parse_app_version(text: str) -> Version:
    """Parse an app version string from App Settings (or similar UI text).

    Strips a leading ``v`` and ignores trailing marketing copy when a semver-like
    token is present. Raises ``ValueError`` when no valid version can be found.
    """
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Empty app version string")

    try:
        return Version(raw.lstrip("vV"))
    except InvalidVersion:
        pass

    match = _VERSION_TOKEN.search(raw)
    if match is None:
        raise ValueError(f"Could not parse app version from {text!r}")
    try:
        return Version(match.group("ver"))
    except InvalidVersion as exc:
        raise ValueError(f"Could not parse app version from {text!r}") from exc


def has_device_details_tabs(version: Version) -> bool:
    """Return True when Device Details uses Hardware / Deck / Run History tabs.

    Production desktop apps gained the tabs after 9.1.2. OT3 builds rebased to a
    4.x line (e.g. ``4.0.0-alpha.10``) already include the same layout.
    """
    if version > DEVICE_DETAILS_TABS_AFTER:
        return True
    return version.major == 4

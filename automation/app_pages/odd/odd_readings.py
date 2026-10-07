"""Values read off the Flex ODD, shared for one Playwright page.

Every ODD page object writes through ``OddShell.readings``, so a later step
can read network details, the robot version, or protocol run records without
opening that screen again.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from playwright.sync_api import Page


@dataclass(frozen=True)
class ProtocolRunRecord:
    """One row on File Manager → Protocol Run Records."""

    protocol_name: str
    last_run_date: str
    run_status: str


@dataclass
class OddReadings:
    """Collected ODD values for the page attached to this test."""

    network: dict[str, str] = field(default_factory=dict)
    robot_system_version: str = ""
    protocol_run_records: list[ProtocolRunRecord] = field(default_factory=list)
    instrument: dict[str, str] = field(default_factory=dict)


_by_page: dict[int, OddReadings] = {}


def readings_for(page: Page) -> OddReadings:
    """Return the reading store for ``page``, creating it on first use."""
    key = id(page)
    store = _by_page.get(key)
    if store is None:
        store = OddReadings()
        _by_page[key] = store
    return store

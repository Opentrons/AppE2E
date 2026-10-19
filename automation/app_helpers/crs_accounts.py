"""Lab account used by Compliance Ready Software tests.

Change the default user here. ``CRS_USERNAME`` and ``CRS_PASSWORD`` override
those defaults for a single run.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CrsAccount:
    """Username and password for a Compliance Ready login."""

    username: str
    password: str

    @property
    def account_initial(self) -> str:
        """First letter shown on the signed-in account button."""
        return self.username[:1].upper()


def load_crs_account() -> CrsAccount:
    """Return the lab account, with optional environment overrides."""
    return CrsAccount(
        username=os.environ.get("CRS_USERNAME", "testadmin"),
        password=os.environ.get("CRS_PASSWORD", "testadminpassword"),
    )

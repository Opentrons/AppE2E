"""Lab account used by Compliance Ready Software tests.

Change the default user here. ``CRS_USERNAME``, ``CRS_PASSWORD``, and
``CRS_LEGAL_NAME`` override those defaults for a single run.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import asdict, dataclass

from automation.app_helpers.test_progress import emit_event, log_info


@dataclass(frozen=True)
class CrsAccount:
    """Username and password for a Compliance Ready login."""

    username: str
    password: str
    legal_name: str = "test admin"

    @property
    def account_initial(self) -> str:
        """First letter shown on the signed-in account button."""
        return self.username[:1].upper()


@dataclass(frozen=True)
class CrsReportedAccount:
    """One account to show in the workflow runner after Enable CRS."""

    role: str
    username: str
    password: str
    legal_name: str = ""


def load_crs_account() -> CrsAccount:
    """Return the lab account, with optional environment overrides."""
    return CrsAccount(
        username=os.environ.get("CRS_USERNAME", "testadmin"),
        password=os.environ.get("CRS_PASSWORD", "testadminpassword"),
        legal_name=os.environ.get("CRS_LEGAL_NAME", "test admin"),
    )


def report_crs_accounts(accounts: Sequence[CrsReportedAccount], *, service_pin: str = "") -> None:
    """Print Enable CRS credentials and send them to the workflow runner."""
    for account in accounts:
        legal = f" ({account.legal_name})" if account.legal_name else ""
        log_info(f"{account.role}: username {account.username}{legal} / password {account.password}")
    if service_pin:
        log_info(f"Service PIN: {service_pin}")
    emit_event(
        {
            "type": "credentials",
            "service_pin": service_pin,
            "accounts": [asdict(account) for account in accounts],
        }
    )

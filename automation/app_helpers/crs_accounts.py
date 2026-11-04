"""Lab accounts used by Compliance Ready Software tests.

``report_crs_accounts`` prints credentials, sends them to the workflow runner,
and writes ``artifacts/crs_accounts.json``. That file is kept until the next
Enable CRS run overwrites it. Login tests load Service / Admin / Recovery from
there. ``CRS_USERNAME``, ``CRS_PASSWORD``, and ``CRS_LEGAL_NAME`` still override
the Admin account for a single process.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from automation.app_helpers.test_progress import emit_event, log_info

ROOT = Path(__file__).resolve().parents[2]
CRS_ACCOUNTS_PATH = ROOT / "artifacts" / "crs_accounts.json"


@dataclass(frozen=True)
class CrsAccount:
    """Username and password for a Compliance Ready login."""

    username: str
    password: str
    legal_name: str = "test admin"
    role: str = "Admin"

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

    def as_login(self) -> CrsAccount:
        """Convert to the login shape used by fixtures and page objects."""
        return CrsAccount(
            username=self.username,
            password=self.password,
            legal_name=self.legal_name,
            role=self.role,
        )


def credentials_event(*, accounts: Sequence[CrsReportedAccount], service_pin: str = "") -> dict[str, object]:
    """Build the structured credentials event for the workflow runner."""
    return {
        "type": "credentials",
        "service_pin": service_pin,
        "accounts": [asdict(account) for account in accounts],
    }


def save_crs_accounts(accounts: Sequence[CrsReportedAccount], *, service_pin: str = "") -> Path:
    """Write accounts to disk, replacing any previous Enable CRS credentials."""
    path = CRS_ACCOUNTS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "service_pin": service_pin,
        "accounts": [asdict(account) for account in accounts],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load_saved_credentials_event() -> dict[str, object] | None:
    """Return the last saved credentials event, or None when nothing is stored."""
    path = CRS_ACCOUNTS_PATH
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    accounts = payload.get("accounts")
    if not isinstance(accounts, list) or not accounts:
        return None
    service_pin = payload.get("service_pin") or ""
    return {
        "type": "credentials",
        "service_pin": service_pin if isinstance(service_pin, str) else "",
        "accounts": accounts,
    }


def load_saved_crs_accounts() -> list[CrsReportedAccount]:
    """Return saved Enable CRS accounts, or an empty list when none are stored."""
    event = load_saved_credentials_event()
    if event is None:
        return []
    accounts: list[CrsReportedAccount] = []
    for raw in event.get("accounts", []):
        if not isinstance(raw, dict):
            continue
        role = str(raw.get("role") or "").strip()
        username = str(raw.get("username") or "").strip()
        password = str(raw.get("password") or "").strip()
        if not role or not username or not password:
            continue
        accounts.append(
            CrsReportedAccount(
                role=role,
                username=username,
                password=password,
                legal_name=str(raw.get("legal_name") or ""),
            )
        )
    return accounts


def load_crs_account_role(role: str) -> CrsAccount | None:
    """Return the saved account for ``role`` (Service, Admin, Recovery), if any."""
    wanted = role.strip().casefold()
    for account in load_saved_crs_accounts():
        if account.role.casefold() == wanted:
            return account.as_login()
    return None


def load_crs_account() -> CrsAccount:
    """Return the Admin lab account: env overrides, then saved file, then defaults."""
    saved = load_crs_account_role("Admin")
    return CrsAccount(
        username=os.environ.get("CRS_USERNAME", saved.username if saved else "testadmin"),
        password=os.environ.get("CRS_PASSWORD", saved.password if saved else "testadminpassword"),
        legal_name=os.environ.get("CRS_LEGAL_NAME", saved.legal_name if saved else "test admin"),
        role="Admin",
    )


def report_crs_accounts(accounts: Sequence[CrsReportedAccount], *, service_pin: str = "") -> None:
    """Persist, print, and send Enable CRS credentials to the workflow runner."""
    save_crs_accounts(accounts, service_pin=service_pin)
    for account in accounts:
        legal = f" ({account.legal_name})" if account.legal_name else ""
        log_info(f"{account.role}: username {account.username}{legal} / password {account.password}")
    if service_pin:
        log_info(f"Service PIN: {service_pin}")
    emit_event(credentials_event(accounts=accounts, service_pin=service_pin))

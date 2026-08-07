---
name: app-e2e
description: >-
  Opentrons desktop app (Electron) Playwright E2E tests in this standalone
  workspace. Use when writing, running, or modifying tests under tests/app/,
  page objects in automation/app_pages/, helpers in automation/app_helpers/,
  or make test-app* targets.
---

# App E2E (Standalone Workspace)

## Working tree vs monorepo

- **Edit and run tests here** — this folder is a personal working copy of monorepo `e2e-testing/`.
- **Monorepo (read-only reference):** `/Users/alexcopperman/Downloads/Opentrons_General/opentrons`

When you need UI structure, `data-testid`s, or Electron behavior, look in the monorepo — do not copy app source into this workspace.

### Useful monorepo paths

| Path | Use for |
| --- | --- |
| `app/src/` | Electron renderer UI, screens, routes |
| `components/src/` | Shared UI primitives and test IDs |
| `app-shell/` | Electron main process (launch / CDP issues only) |

Full paths:

- `/Users/alexcopperman/Downloads/Opentrons_General/opentrons/app/src/`
- `/Users/alexcopperman/Downloads/Opentrons_General/opentrons/components/src/`
- `/Users/alexcopperman/Downloads/Opentrons_General/opentrons/app-shell/`

## How to run

```bash
make setup test-setup          # once
make configure-robot           # interactive .env (robot IP / name)
make test-app-headed           # packaged Opentrons.app over CDP
make test-app-device-cards-headed
make test-app-nav-headed
make test-app-headed PYTEST_ARGS="-k test_devices_nav"
make test-odd-headed ROBOT_IP=<flex-ip>   # ODD CDP (Developer Tools on)
make test-odd-headed PYTEST_ARGS="--robot-ip <flex-ip>"
```

Default launch is the **installed** Opentrons app (`/Applications/Opentrons.app/...`) with remote debugging on port 9222.

For **dev app + local robot-server** (`--robot-profile fake-robot`), set in `.env`:

```bash
OPENTRONS_ROOT=/Users/alexcopperman/Downloads/Opentrons_General/opentrons
```

`open_app.find_monorepo_root()` prefers `OPENTRONS_ROOT`, then walk-up discovery.

## Layout (this workspace)

- `tests/app/` — app E2E tests (`nav/`, `device_cards/`, `abr_orchestration/`)
- `automation/app_pages/` — page objects (import from `automation.app_pages`)
- `automation/app_helpers/` — robot connection, reporting, launch helpers
- `automation/base_page.py` — shared `BasePage` (via `AppBasePage`)
- `open_app.py` — launch / attach Electron over CDP
- `tests/app/conftest.py` — `run_local_app`, robot fixtures, artifacts
- `tests/odd/` — Flex ODD CDP tests

Protocol Designer / Labware Library suites are **not** in this workspace (see monorepo `e2e-testing/`).

## Conventions

- **ALWAYS** use Page Object Model — no raw Playwright selectors in test files
- Put selectors and UI flows in `automation/app_pages/`; shared helpers in `automation/app_helpers/`
- Prefer `get_by_role` / `get_by_test_id` / `get_by_text` over CSS/XPath
- Wait with Playwright `expect` or page-object helpers — avoid `time.sleep()`
- Type-annotate public helpers; keep tests independent (no shared mutable state)

### Example

```python
from playwright.sync_api import Page
from automation.app_helpers.test_progress import log_done, log_step
from automation.app_pages import DevicesPage


def test_devices_nav(run_local_app: Page, robot_name: str) -> None:
    page = run_local_app
    log_step("Open Devices")
    devices = DevicesPage(page)
    devices.open()
    log_done("Devices visible")
```

## Syncing back to the monorepo

Changes here are independent. When ready to upstream, copy or cherry-pick into:

`/Users/alexcopperman/Downloads/Opentrons_General/opentrons/e2e-testing/`

There is no automatic two-way sync.

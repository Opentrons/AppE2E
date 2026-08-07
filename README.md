# Opentrons App E2E

End-to-end Playwright tests for the **Opentrons desktop app (Electron)** and **Flex ODD** (on-device display).

Protocol Designer and Labware Library suites live in the monorepo (`opentrons/e2e-testing/`), not here.

## Workspace

| | Path |
| --- | --- |
| This workspace | `/Users/alexcopperman/Downloads/Opentrons_General/opentrons-app-e2e` |
| Monorepo (UI reference) | `/Users/alexcopperman/Downloads/Opentrons_General/opentrons` |

Edit and run app/ODD tests here. Treat the monorepo as read-only for UI source and `data-testid`s (`app/src/`, `components/src/`, `app-shell/`).

## Prerequisites

- Python 3.12
- [uv](https://github.com/astral-sh/uv)
- Installed Opentrons desktop app (for `make test-app*`)
- Connected Flex (USB or Wi-Fi), or `fake-robot` with monorepo `OPENTRONS_ROOT`

## Quick start

```bash
make setup test-setup
make configure-robot                 # robot IP / name → .env
make test-app-headed                 # packaged Opentrons.app, headed
make test-app-headed PYTEST_ARGS="-k test_temperature_module_card"
```

For `fake-robot` / `make -C app dev`, set in `.env`:

```bash
OPENTRONS_ROOT=/Users/alexcopperman/Downloads/Opentrons_General/opentrons
```

## Running tests

### Desktop app (Electron over CDP)

```bash
make configure-robot                             # Interactive .env setup
make check-robot                                 # Verify robot connectivity
make test-app                                    # Full app suite
make test-app-headed                             # Headed Electron window
make test-app-nav-headed                         # Navigation smoke
make test-app-device-cards-headed                # Device card exercises
make test-app-headed PYTEST_ARGS="-k test_name"  # One test
make run_abr_2_and_4                             # ABR2/ABR4 orchestration
```

### Flex ODD (touchscreen over CDP)

Enable **Developer Tools** on the robot, then attach to port **9223**:

```bash
make test-odd-headed                             # uses ROBOT_IP from .env
make test-odd-headed ROBOT_IP=10.14.19.200
make test-odd-headed PYTEST_ARGS="--robot-ip 10.14.19.200"
```

### Tips

- Use `page.pause()` or headed failures (auto-pause) to debug selectors.
- Re-run last failures: `make troubleshoot`
- Agents: use `.cursor/skills/app-e2e/` when working on app tests.

## Directory layout

- `automation/app_pages/` — Desktop app + ODD page objects
- `automation/app_helpers/` — Launch, robot connection, reporting
- `automation/base_page.py` — Shared `BasePage`
- `tests/app/` — Desktop app tests (`nav/`, `device_cards/`, `calibration/`, `abr_orchestration/`)
- `tests/odd/` — Flex ODD CDP tests
- `open_app.py`, `configure_robot.py`, `main_script.py` — Electron launch utilities
- `conftest.py` — Shared pytest hooks (headed pause-on-failure)
- `tests/app/conftest.py` — `run_local_app`, robot fixtures, artifacts

## Code quality

```bash
make format
make typecheck
make check                   # lint + typecheck
make prep                    # format + typecheck
```

## Artifacts

- HTML report: `test-results/report.html`
- Videos: `test-results/videos/` (headed runs)
- Traces: `test-results/traces/`

Do not commit `test-results/` (gitignored).

## Upstream

When ready, copy or cherry-pick into monorepo `e2e-testing/`. There is no automatic two-way sync.

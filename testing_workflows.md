# Testing Workflows

## Executive summary

This repo automates **Opentrons desktop app (Electron) E2E** against a real Flex (or configured robot) via Playwright over CDP, plus **robot system update/downgrade** via the vendored update API tooling (not the app UI).

### Magnitude (what is automated)

| Area | Approx. automated cases | What it proves |
| --- | --- | --- |
| **Robot Settings** | ~12 active flows (T69745–T69755 + Analytics + Home gantry) | Calibration, networking, camera/privacy, advanced settings, destructive Device Reset |
| **File manager** | 4 flows | Capacity snapshot, run records, diagnostics, calibration logs |
| **Hardware cards** | 7 flows (T70399 / T70554 + modules + lights) | Pipette / gripper / module cards and robot lights on robot detail |
| **Deck + run history** | 2 flows (C607-adjacent + run history) | Deck Configuration labels; Run History download control |
| **App Settings** | 10 TestRail cases across 4 tab tests (T69757–T69766, T69848) + 1 advanced preference | Gear-menu General / Privacy / Advanced / Feature Flags |
| **Protocols & labware** | 7 flows (+ labware T69770) | Open protocol, detail tabs, reanalyze / send / show in folder / delete cancel, labware landing |
| **Protocol run & setup** | 2 run-surface flows + **5** Setup steps | Run tabs (incl. Module Controls / C722), run header, Instruments → Camera setup |
| **Update / downgrade (robot API)** | Smoke Zip / USB / consecutive downgrade+upgrade (C44434-adjacent) | System image apply over network or USB serial + post-restart health (`Regression_test_tooling`) |

**Rough total:** ~45 Playwright UI flows in `device_cards` / `nav`, **plus** automated Flex system update ↔ downgrade via `update_robot.py` (see section below).

| Suite make target | Scope |
| --- | --- |
| `make test-app-robot-settings-headed` | Robot detail → Robot Settings (Device Reset last) |
| `make test-app-device-cards-headed` | Full `device_cards/` (settings + cards + deck + file manager + run history) |
| `make test-app-nav-headed` | Full `nav/` (App Settings, protocols, labware, run tabs, setup) |
| `update_robot.py --usb --file …` | Real system update / downgrade (not Playwright) |

### Gaps / not fully covered yet (review checklist)

| Item | Status |
| --- | --- |
| **T69751** Pause on door open | Present but **skipped** (OT-2 only; not exercised on Flex) |
| **T69756** Robot Server Reinstall | Exists in code; **omitted from this runbook** (not part of the documented plan) |
| **T69752** | No ticket / no test in repo |
| **App language round-trip** | Placeholder **skipped** (no page-object helper yet) |
| **Module calibration** (T69769–T69771 / C44406–C44408) | Automated under `tests/app/calibration/` (see bottom) — not in `device_cards` / `nav` |
| **ODD / ABR** | Separate suites (`tests/odd/`, `abr_orchestration/`) — out of scope here |
| **C607 Module & Fixture Labels** | Partial: deck config + Setup → Deck Hardware (closest coverage) |
| **App UI update from device page / downgrade via App** | Robot zip path **done** via tooling; full **desktop-app** update wizard still only partial (`test_advanced_update_robot_software`) |

---

## T69755 — Device Reset

**Path:** Robot Settings → Advanced → Device Reset

Select all reset options except **Clear SSH public keys**, then clear data and restart.

**Page object:** `RobotSettingsPage.reset_all_except_ssh()`

```bash
make test-app-headed PYTEST_ARGS="-k test_advanced_device_reset"
```

---

## Robot Settings (T69745–T69755)

Prerequisite (opens robot detail before settings tests):

```bash
make test-app-headed PYTEST_ARGS="-k test_robot_detail_from_devices_list"
```

### T69745 — About Calibration

**Path:** Robot Settings → Calibration → About Calibration

```bash
make test-app-headed PYTEST_ARGS="-k test_calibration_about_calibration"
```

### T69746 — Pipette Calibrations

**Path:** Robot Settings → Calibration → Pipette Calibrations

Calibrate the pipette:

```bash
make test-app-calibration-headed PYTEST_ARGS="-k test_96_channel_calibration"
```

Validate pipette calibrations in Robot Settings:

```bash
make test-app-headed PYTEST_ARGS="-k test_calibration_pipette_calibrations"
```

### T69747 — Networking

**Path:** Robot Settings → Networking

```bash
make test-app-headed PYTEST_ARGS="-k test_networking"
```

### T69748 — Privacy + Camera settings

**Path:** Robot Settings → Camera (Privacy / camera usage)

```bash
make test-app-headed PYTEST_ARGS="-k test_privacy"
```

### Analytics (Camera usage)

**Path:** Robot Settings → Camera → usage / analytics controls

```bash
make test-app-headed PYTEST_ARGS="-k test_analytics"
```

### T69749 — Robot Name

**Path:** Robot Settings → Advanced → Robot Name

```bash
make test-app-headed PYTEST_ARGS="-k test_advanced_robot_name"
```

### T69750 — Robot Server Version

**Path:** Robot Settings → Advanced → Robot server version

```bash
make test-app-headed PYTEST_ARGS="-k test_advanced_robot_server_version"
```

### T69751 — Pause protocol when door opens (skipped on Flex)

**Path:** Robot Settings → Advanced → Pause protocol when robot door opens

OT-2 only; currently `@pytest.mark.skip` on Flex.

```bash
make test-app-headed PYTEST_ARGS="-k test_advanced_pause_on_door_open"
```

### Home gantry

**Path:** Robot Overview overflow → Home gantry (not Advanced Settings)

Runs before protocol-run workflows (Home gantry is disabled while a run is loaded).

```bash
make test-app-headed PYTEST_ARGS="-k test_home_gantry_from_overview_overflow"
```

### T69753 — Jupyter Notebook

**Path:** Robot Settings → Advanced → Jupyter Notebook

```bash
make test-app-headed PYTEST_ARGS="-k test_advanced_jupyter_notebook"
```

### T69754 — Update robot software

**Path:** Robot Settings → Advanced → Update robot software

```bash
make test-app-headed PYTEST_ARGS="-k test_advanced_update_robot_software"
```

### File manager

**Path:** Robot Settings → File manager

| Case | Command filter |
| --- | --- |
| File capacity snapshot | `-k test_file_capacity` |
| Protocol run records | `-k test_protocol_run_records` |
| Diagnostic files | `-k test_diagnostic_files` |
| Download calibration logs | `-k test_download_calibration_logs` |

```bash
make test-app-device-cards-headed PYTEST_ARGS="-k 'file_capacity or protocol_run_records or diagnostic_files or download_calibration_logs'"
```

### Run Robot Settings as a suite

One pytest session (one Electron window): **robot detail first**, then Robot Settings cases, then the app closes.

```bash
make test-app-robot-settings-headed
```

That target collects, in order:

1. `test_devices_nav.py::test_robot_detail_from_devices_list`
2. `test_robot_settings.py` — T69745–T69755 + Analytics + Home gantry (**Device Reset** last)

| Scope | Command |
| --- | --- |
| Full suite (above) | `make test-app-robot-settings-headed` |
| Skip Device Reset | `make test-app-robot-settings-headed PYTEST_ARGS="-k 'not device_reset'"` |
| Calibration only | `make test-app-robot-settings-headed PYTEST_ARGS="-k 'robot_detail or calibration_about or calibration_pipette'"` |
| Networking + Camera | `make test-app-robot-settings-headed PYTEST_ARGS="-k 'robot_detail or networking or privacy or analytics'"` |
| Advanced (no restart) | `make test-app-robot-settings-headed PYTEST_ARGS="-k 'robot_detail or (test_advanced_ and not device_reset)'"` |
| Device Reset only | `make test-app-robot-settings-headed PYTEST_ARGS="-k 'robot_detail or device_reset'"` |

When filtering with `-k`, keep `robot_detail` in the expression so the prerequisite still runs in the same session.

Single case (settings fixture navigates itself): use the `-k test_…` command under each ticket section above.

---

## Device Cards — Instruments, Modules, Deck (T70399 / T70554 / C722 / C607)

Separate from Robot Settings. These live on **robot detail** hardware cards, **Deck Configuration**, and **Protocol Run** — not under Robot Settings tabs.

**Suite files:**
- `tests/app/device_cards/test_cards.py` — pipette / gripper / module cards + lights
- `tests/app/device_cards/test_deck_configuration.py` — deck module & fixture labels
- `tests/app/device_cards/test_run_history.py` — Run History tab
- `tests/app/nav/test_protocol_run_tabs.py` — Protocol Run tabs (includes Module Controls)
- `tests/app/nav/test_run_setup.py` — Protocol Setup steps (Deck Hardware, etc.)

**Prerequisite:** `test_robot_detail_from_devices_list`

### T70399 — Pipette App: About Pipette

**Path:** Devices → Robot detail → pipette card → About pipette

```bash
make test-app-device-cards-headed PYTEST_ARGS="-k 'test_left_pipette_card or test_right_pipette_card'"
```

### T70554 — Gripper App: About Gripper

**Path:** Devices → Robot detail → gripper card → About gripper

```bash
make test-app-device-cards-headed PYTEST_ARGS="-k test_gripper_card"
```

### Module cards (robot detail controls)

Heater-Shaker / Temperature / Thermocycler cards on robot overview (not Protocol Run Module Controls):

```bash
make test-app-device-cards-headed PYTEST_ARGS="-k 'test_thermocycler_module_card or test_heater_shaker_module_card or test_temperature_module_card'"
```

### Robot lights

**Path:** Devices → Robot detail → lights toggle

```bash
make test-app-device-cards-headed PYTEST_ARGS="-k test_robot_lights"
```

### Run History

**Path:** Devices → Robot detail → Run History

Requires Device Details tabs layout.

```bash
make test-app-device-cards-headed PYTEST_ARGS="-k test_run_history"
```

### C722 / C44404 — Devices > Robot > Protocol Run > Module controls

**Path:** Protocol Run → Module Controls tab

Covered when run tabs are captured (Module Controls is one of the tabs):

```bash
make test-app-nav-headed PYTEST_ARGS="-k test_protocol_run_tabs"
```

### C607 — App > Protocol Setup > Module & Fixture Labels

**Closest coverage today:**
- Deck Configuration labels on robot detail → `test_deck_configuration`
- Protocol Setup → Deck Hardware step → `test_run_setup_step` (`Deck Hardware`)

```bash
make test-app-device-cards-headed PYTEST_ARGS="-k test_deck_configuration"
make test-app-nav-headed PYTEST_ARGS="-k 'test_run_setup_step and Deck'"
```

### Run all device-card hardware cases

```bash
make test-app-device-cards-headed PYTEST_ARGS="test_cards.py"
```

Full `device_cards/` folder (settings + cards + deck + file manager + run history):

```bash
make test-app-device-cards-headed
```

---

## App Settings (T69757–T69766 / T69848) — `tests/app/nav`

**Path:** App gear menu → App Settings tabs

| Ticket | Area | Covered by |
| --- | --- | --- |
| T69758 / T69765 / T69766 | General — connect via IP, Update, Software Update Alerts | `test_general_tab` |
| T69848 | Privacy — Share App Analytics | `test_privacy_tab` |
| T69760–T69764 | Advanced — channel, labware folder, unavailable robots, clear, developer tools | `test_advanced_tab` |
| T69757 | Feature flags | `test_feature_flags_tab` |
| — | Include protocol source in run download (preference toggle) | `test_protocol_source_download_preference` |
| — | Change language and restore English | `test_app_language_round_trip` (**skipped**) |

```bash
make test-app-nav-headed PYTEST_ARGS="-k 'test_general_tab or test_privacy_tab or test_advanced_tab or test_feature_flags_tab'"
make test-app-nav-headed PYTEST_ARGS="-k test_protocol_source_download_preference"
```

---

## Protocols & Labware — `tests/app/nav`

### Protocols

| Flow | Filter |
| --- | --- |
| Open protocol from landing | `-k test_protocol_opens_from_landing` |
| Protocol detail tabs (screenshots) | `-k test_protocol_detail_tabs` |
| Reanalyze | `-k test_protocol_reanalyze` |
| Send to Opentrons Flex | `-k test_protocol_send_to_flex` |
| Show in folder | `-k test_protocol_show_in_folder` |
| Delete protocol (cancel) | `-k test_protocol_delete_cancel` |

```bash
make test-app-nav-headed PYTEST_ARGS="-k 'test_protocol_opens or test_protocol_detail or test_protocol_reanalyze or test_protocol_send or test_protocol_show or test_protocol_delete'"
```

### Labware (T69770 — labware landing)

**Path:** Labware landing → scroll / browse

> Note: T69770 is also used in TestRail for Temperature Module calibration; labware landing reuses that ID in code.

```bash
make test-app-nav-headed PYTEST_ARGS="-k test_labware_landing"
```

---

## Protocol Run & Setup — `tests/app/nav`

### Protocol Run tabs + header

| Flow | Filter |
| --- | --- |
| Screenshot Protocol Run tabs (incl. Module Controls) | `-k test_protocol_run_tabs` |
| Read run status and timer | `-k test_protocol_run_header` |

```bash
make test-app-nav-headed PYTEST_ARGS="-k 'test_protocol_run_tabs or test_protocol_run_header'"
```

### Protocol Setup steps

Parametrized `test_run_setup_step` — one case per step:

1. Instruments  
2. Deck Hardware  
3. Labware Offsets  
4. Labware & Liquids  
5. Camera  

```bash
make test-app-nav-headed PYTEST_ARGS="-k test_run_setup_step"
```

### Run full nav suite

```bash
make test-app-nav-headed
```

---

## T69769 / T69770 / T69771 — Module Calibration

Outside `device_cards` / `nav` (`tests/app/calibration/`):

- **T69769** — Thermocycler (TC) calibration  
- **T69770** — Temperature Module (TD) calibration  
- **T69771** — Heater-Shaker (HS) calibration  

Also tagged in code as C44406 / C44407 / C44408.

```bash
make test-app-calibration-headed PYTEST_ARGS="-k 'heater_shaker or temperature_module or thermocycler'"
```

---

## Smoke — Update/downgrade: Zip / USB / network (**done**)

**Status: automated** (robot update API — not Playwright). Maps to Smoke Test V2 / Flex cases such as **Update with Zip**, **Update via USB**, **Downgrade via Zip**, and consecutive **downgrade/upgrade** (C44434-adjacent).

**Tooling:** `.cursor/skills/Regression_test_tooling/` — see [`SKILL.md`](.cursor/skills/Regression_test_tooling/SKILL.md) and [`scripts/update_robot.py`](.cursor/skills/Regression_test_tooling/scripts/update_robot.py). Supporting modules: `update_robot_session.py`, `update_robot_verifications.py`, `update_robot_phases.py`, `check_health.py`.

| Smoke-ish case | How we cover it |
| --- | --- |
| Update via USB | `update_robot.py --usb --file ot3-system-….zip` |
| Update with Zip / from local file | `--file` over USB or network IP |
| Downgrade via Zip | Consecutive `--file` older version after a newer one |
| Downgrade/upgrade round-trip | Multiple `--file` in order (script waits for health between each) |
| App > Update from device page | **Partial** — Playwright `test_advanced_update_robot_software` (panel only) |
| Downgrade via App | **Not** automated in the desktop UI |

### Prerequisites

- Flex connected over USB (for `--usb`) **or** reachable by IP (network path)
- For USB: close the Opentrons desktop app (it holds the serial port)
- Place system zips under `.cursor/skills/Regression_test_tooling/scripts/` (or pass absolute `--file` paths) — **zips are not committed**
- Deps: `python3 -m pip install httpx pyserial` (same interpreter you run)

### Consecutive USB update → downgrade → update

Script waits for the robot to come back between each zip (health / readiness checks), then continues.

```bash
# From this workspace root (opentrons-app-e2e)
python .cursor/skills/Regression_test_tooling/scripts/update_robot.py --usb \
  --file .cursor/skills/Regression_test_tooling/scripts/ot3-system-9.0.0-alpha.12.zip \
  --file .cursor/skills/Regression_test_tooling/scripts/ot3-system-8.7.0.zip \
  --file .cursor/skills/Regression_test_tooling/scripts/ot3-system-9.0.0-alpha.12.zip \
  -y
```

Sequence: **9.0.0-alpha.12 → 8.7.0 → 9.0.0-alpha.12**.

Network equivalent (robot on Wi‑Fi/Ethernet):

```bash
python .cursor/skills/Regression_test_tooling/scripts/update_robot.py <ROBOT_IP> \
  --file /path/to/ot3-system-8.7.0.zip \
  --file /path/to/ot3-system-9.0.0-alpha.12.zip \
  -y
```

### Notes

- Skill frontmatter still says `robot-ip-health`; on disk the folder is `Regression_test_tooling/`.
- Single zip: same command with one `--file`. Debug serial I/O with `--debug-usb`.
- Catalog page (`test_catalog.html`) lists these scripts under **tooling** so they show up next to Playwright tests.

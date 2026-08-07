# Opentrons desktop app + ODD E2E testing

ifneq (,$(wildcard .env))
include .env
export
endif

HEADED ?=
PYTEST_ARGS ?=
PYTEST_HEADED := $(if $(HEADED),HEADED=1,)

.PHONY: setup test-setup format lint typecheck prep check \
	configure-robot check-robot \
	_pytest-app _app-report-banner \
	test-app test-app-headed test-app-nav test-app-nav-headed \
	test-app-device-cards test-app-device-cards-headed run_abr_2_and_4 \
	test-odd test-odd-headed \
	troubleshoot

# --- Setup & quality ---

setup:
	uv sync --frozen

test-setup:
	uv run playwright install chromium --with-deps

format:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy automation tests conftest.py

prep: format typecheck

check: lint typecheck

# --- Robot & app (Electron) ---

configure-robot:
	uv run python configure_robot.py

check-robot:
	uv run python -m automation.app_helpers.robot_connection $(ROBOT_IP)

_pytest-app:
	@status=0; \
	$(HEADED_ENV) uv run pytest $(TEST_PATH) $(PYTEST_ARGS) || status=$$?; \
	$(MAKE) --no-print-directory _app-report-banner; \
	exit $$status

test-app:
	@$(MAKE) --no-print-directory _pytest-app TEST_PATH=tests/app/ HEADED_ENV="$(PYTEST_HEADED)"

test-app-headed:
	@$(MAKE) --no-print-directory _pytest-app TEST_PATH=tests/app/ HEADED_ENV="HEADED=1"

test-app-nav:
	@$(MAKE) --no-print-directory _pytest-app TEST_PATH=tests/app/nav/ HEADED_ENV="$(PYTEST_HEADED)"

test-app-nav-headed:
	@$(MAKE) --no-print-directory _pytest-app TEST_PATH=tests/app/nav/ HEADED_ENV="HEADED=1"

test-app-device-cards:
	@$(MAKE) --no-print-directory _pytest-app TEST_PATH=tests/app/device_cards/ HEADED_ENV="$(PYTEST_HEADED)"

test-app-device-cards-headed:
	@$(MAKE) --no-print-directory _pytest-app TEST_PATH=tests/app/device_cards/ HEADED_ENV="HEADED=1"

# Flex ODD (remote CDP on ROBOT_IP:9223 — enable Developer Tools on the touchscreen first)
# Examples:
#   make test-odd-headed ROBOT_IP=10.14.19.200
#   make test-odd-headed PYTEST_ARGS="--robot-ip 10.14.19.200"
test-odd:
	@$(MAKE) --no-print-directory _pytest-app TEST_PATH=tests/odd/ HEADED_ENV="$(PYTEST_HEADED)"

test-odd-headed:
	@$(MAKE) --no-print-directory _pytest-app TEST_PATH=tests/odd/ HEADED_ENV="HEADED=1"

run_abr_2_and_4:
	@$(MAKE) --no-print-directory _pytest-app \
		TEST_PATH=tests/app/abr_orchestration/test_abr_2_and_4.py HEADED_ENV="HEADED=1"

troubleshoot:
	@echo "Re-running last failures in headed mode..."
	-HEADED=1 uv run pytest --lf -s --tb=short

_app-report-banner:
	@echo ""
	@echo "---------------------------------------------------------"
	@echo "App tests finished."
	@echo "Open test-results/report.html for the HTML report."
	@echo "Videos: test-results/videos/ (headed runs)"
	@echo "Traces: test-results/traces/"
	@echo "---------------------------------------------------------"

# Opentrons E2E testing

ifneq (,$(wildcard .env))
include .env
export
endif

TEST_ENV ?= local
HEADED ?=
PYTEST_ARGS ?=
PYTEST_HEADED := $(if $(HEADED),HEADED=1,)

.PHONY: setup test-setup format lint typecheck prep check \
	configure-robot check-robot \
	_pytest-app _app-report-banner _e2e-report-banner \
	test-app test-app-headed test-app-nav test-app-nav-headed \
	test-app-device-cards test-app-device-cards-headed run_abr_2_and_4 \
	test-odd test-odd-headed \
	troubleshoot _pytest-mark \
	test-pd-local test-pd-local-headed test-pd-sandbox test-pd-staging \
	test-pd-staging-headed test-pd-prod test-pd-debug \
	test-ll-local test-ll test-ll-local-headed test-ll-staging \
	test-ll-staging-headed test-ll-prod \
	test-unit test-compare codegen

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

_app-report-banner:
	@echo ""
	@echo "---------------------------------------------------------"
	@echo "App tests finished."
	@echo "Open test-results/report.html for the HTML report."
	@echo "Videos: test-results/videos/ (headed runs)"
	@echo "Traces: test-results/traces/"
	@echo "---------------------------------------------------------"

# --- Protocol Designer (PD) ---

_pytest-mark:
	TEST_ENV=$(TEST_ENV) $(HEADLESS_ENV) uv run pytest -m $(MARKER) $(PYTEST_ARGS) $(EXTRA_ARGS)

test-pd-local:
	@status=0; \
	TEST_ENV=local uv run pytest -m pdE2E $(PYTEST_ARGS) || status=$$?; \
	$(MAKE) --no-print-directory _e2e-report-banner; \
	exit $$status

troubleshoot:
	@echo "Re-running last failures in headed mode..."
	-TEST_ENV=local uv run pytest --lf --headed -s --tb=short

test-pd-local-headed:
	@echo "Example: make test-pd-local-headed PYTEST_ARGS=\"-k test_flex_onboarding_workflow\""
	@$(MAKE) --no-print-directory _pytest-mark TEST_ENV=local MARKER=pdE2E HEADLESS_ENV="HEADLESS=false"

test-pd-sandbox:
	@echo "TODO: Implement sandbox testing with branch-specific URL"
	@exit 1

test-pd-staging:
	@$(MAKE) --no-print-directory _pytest-mark TEST_ENV=staging MARKER=pdE2E

test-pd-staging-headed:
	@$(MAKE) --no-print-directory _pytest-mark TEST_ENV=staging MARKER=pdE2E HEADLESS_ENV="HEADLESS=false"

test-pd-prod:
	@$(MAKE) --no-print-directory _pytest-mark TEST_ENV=prod MARKER=pdE2E

test-pd-debug:
	@$(MAKE) --no-print-directory _pytest-mark TEST_ENV=$(TEST_ENV) MARKER=pdE2E \
		EXTRA_ARGS="-v --headed --slowmo=1000 -s"

_e2e-report-banner:
	@echo ""
	@echo "---------------------------------------------------------"
	@echo "Tests finished."
	@echo "Open test-results/report.html for the HTML report."
	@echo "Run 'make troubleshoot' to re-run last failures in headed mode."
	@echo "---------------------------------------------------------"

# --- Labware Library (LL) ---

test-ll-local:
	@$(MAKE) --no-print-directory _pytest-mark TEST_ENV=local MARKER=llE2E

test-ll:
	@$(MAKE) --no-print-directory _pytest-mark TEST_ENV=$(TEST_ENV) MARKER=llE2E

test-ll-local-headed:
	@$(MAKE) --no-print-directory _pytest-mark TEST_ENV=local MARKER=llE2E HEADLESS_ENV="HEADLESS=false"

test-ll-staging:
	@$(MAKE) --no-print-directory _pytest-mark TEST_ENV=staging MARKER=llE2E

test-ll-staging-headed:
	@$(MAKE) --no-print-directory _pytest-mark TEST_ENV=staging MARKER=llE2E HEADLESS_ENV="HEADLESS=false"

test-ll-prod:
	@$(MAKE) --no-print-directory _pytest-mark TEST_ENV=prod MARKER=llE2E

# --- Misc ---

codegen:
	@echo "Starting Playwright codegen - record your test actions"
	@echo "Target URL: $(or $(URL),http://localhost:4173)"
	uv run playwright codegen --target python $(or $(URL),http://localhost:4173)

test-unit:
	@$(MAKE) --no-print-directory _pytest-mark TEST_ENV=$(TEST_ENV) MARKER=unit

test-compare:
	HEADLESS=$(if $(filter false,$(HEADLESS)),false,true) uv run pytest -m compare_versions \
		--browser chromium tests/pd $(PYTEST_ARGS) -s

"""Reuse the Electron app fixtures from the desktop suite."""

from __future__ import annotations

# Pull in run_local_app / playwright launch from tests/app/conftest.py
pytest_plugins = ["tests.app.conftest"]

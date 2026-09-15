"""Interactive Playwright Inspector for recording compliance / app flows.

Run (headed, keep stdin attached)::

    HEADED=1 uv run pytest tests/compliance/example_test.py -s

In the Inspector: click Record, drive the Opentrons window, copy the generated steps.
Resume / stop the Inspector when finished (the test ends after ``page.pause()`` returns).
"""

from __future__ import annotations

from playwright.sync_api import Page

from automation.app_helpers.test_progress import log_step


def test_explore(run_local_app: Page) -> None:
    """Attach to the Opentrons app and pause for Playwright Inspector recording."""
    page = run_local_app
    log_step("Opentrons app ready — opening Playwright Inspector (Record in the UI)")
    try:
        page.bring_to_front()
    except Exception:
        pass
    page.pause()

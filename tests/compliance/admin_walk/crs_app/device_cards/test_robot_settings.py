"""CRS Admin mirror of ``tests.app.device_cards.test_robot_settings`` — same workflows, logged in as Admin."""

# Star-import only pulls public names; keep fixtures listed so CRS collection
# cannot regress if a shared helper is renamed with a leading underscore again.
from tests.app.device_cards.test_robot_settings import *  # noqa: F403
from tests.app.device_cards.test_robot_settings import (  # noqa: F401
    robot_settings,
    robot_settings_page,
)
"""Page objects for the Flex On-Device Display (ODD).

Every screen inherits ``OddShell``, which clicks the top nav and waits for
the route. Use that to move between dashboard, Protocols, Instruments,
Settings, and the kebab menu without raw selectors in tests.
"""

from automation.app_pages.odd.instruments import OddInstrumentsPage
from automation.app_pages.odd.odd_home_page import OddHomePage
from automation.app_pages.odd.odd_kebab_menu import OddKebabMenu
from automation.app_pages.odd.odd_protocols_page import OddProtocolsPage
from automation.app_pages.odd.odd_settings_page import OddSettingsPage
from automation.app_pages.odd.odd_shell import OddShell

__all__ = [
    "OddHomePage",
    "OddInstrumentsPage",
    "OddKebabMenu",
    "OddProtocolsPage",
    "OddSettingsPage",
    "OddShell",
]

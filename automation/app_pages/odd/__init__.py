"""Page objects for the Flex On-Device Display (ODD).

Every screen inherits ``OddShell``, which clicks the top nav and waits for
the route. Use that to move between dashboard, Protocols, Instruments,
Settings, and the kebab menu without raw selectors in tests.
"""

from automation.app_pages.odd.instruments import OddInstrumentsPage
from automation.app_pages.odd.odd_deck_configuration import OddDeckConfigurationPage
from automation.app_pages.odd.odd_drop_tip_wizard import OddDropTipWizard
from automation.app_pages.odd.odd_home_page import OddHomePage
from automation.app_pages.odd.odd_kebab_menu import OddKebabMenu
from automation.app_pages.odd.odd_protocol_section import OddProtocolOptions, ProtocolSection
from automation.app_pages.odd.odd_protocols_page import OddProtocolsPage
from automation.app_pages.odd.odd_readings import OddReadings, ProtocolRunRecord
from automation.app_pages.odd.odd_settings import LanguageToggle
from automation.app_pages.odd.odd_settings_page import OddSettingsPage
from automation.app_pages.odd.odd_shell import OddShell
from automation.app_pages.odd.odd_unboxing import OddUnboxingPage

__all__ = [
    "LanguageToggle",
    "OddDeckConfigurationPage",
    "OddDropTipWizard",
    "OddHomePage",
    "OddInstrumentsPage",
    "OddKebabMenu",
    "OddProtocolOptions",
    "OddProtocolsPage",
    "OddReadings",
    "OddSettingsPage",
    "OddShell",
    "OddUnboxingPage",
    "ProtocolRunRecord",
    "ProtocolSection",
]

from automation.app_pages.base_app.app_base_page import AppBasePage
from automation.app_pages.base_app.app_settings_page import AppSettingsPage
from automation.app_pages.base_app.choose_robot_slideout import ChooseRobotToRunProtocolSlideout
from automation.app_pages.base_app.deck_configuration_page import DeckConfigurationPage
from automation.app_pages.base_app.device_cards_page import (
    FLEX_STACKER,
    HEATER_SHAKER,
    PLATE_READER,
    TEMPERATURE,
    THERMOCYCLER,
    DeviceCardsPage,
    FlexStackerCard,
    HeaterShakerCard,
    ModuleCard,
    ModuleCardSpec,
    PlateReaderCard,
    TemperatureModuleCard,
    ThermocyclerCard,
)
from automation.app_pages.base_app.devices_page import DevicesPage
from automation.app_pages.base_app.file_manager_page import FileManagerPage
from automation.app_pages.base_app.labware_page import LabwarePage
from automation.app_pages.base_app.protocol_overflow_menu import ProtocolOverflowMenu
from automation.app_pages.base_app.protocol_run_page import ProtocolRunPage
from automation.app_pages.base_app.protocols_page import ProtocolsPage
from automation.app_pages.base_app.robot_settings_page import RobotSettingsPage
from automation.app_pages.base_app.run_history_page import RunHistoryPage
from automation.app_pages.base_app.run_setup_page import RunSetupPage

__all__ = [
    "AppBasePage",
    "AppSettingsPage",
    "ChooseRobotToRunProtocolSlideout",
    "DeckConfigurationPage",
    "DeviceCardsPage",
    "DevicesPage",
    "FLEX_STACKER",
    "FileManagerPage",
    "FlexStackerCard",
    "HEATER_SHAKER",
    "HeaterShakerCard",
    "LabwarePage",
    "ModuleCard",
    "ModuleCardSpec",
    "PLATE_READER",
    "PlateReaderCard",
    "ProtocolOverflowMenu",
    "ProtocolRunPage",
    "ProtocolsPage",
    "RobotSettingsPage",
    "RunHistoryPage",
    "RunSetupPage",
    "TEMPERATURE",
    "THERMOCYCLER",
    "TemperatureModuleCard",
    "ThermocyclerCard",
]

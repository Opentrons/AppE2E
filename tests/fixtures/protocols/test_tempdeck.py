from opentrons import protocol_api

requirements = {"apiLevel": "2.28", "robotType": "Flex"}
metadata = {"protocolName": "Protocol 1: Temperature Module Disconnect Recovery Test"}


def run(protocol: protocol_api.ProtocolContext) -> None:
    temp_module = protocol.load_module("temperature module gen2", "D1")
    temp_adapter = temp_module.load_adapter("opentrons_96_well_aluminum_block")
    temp_labware = temp_adapter.load_labware("opentrons_96_wellplate_200ul_pcr_full_skirt")

    protocol.comment("Temperature Module loaded in D1. Starting test sequence.")
    temp_module.set_temperature(80)

    for i in range(1, 2):
        temp_module.set_temperature(40)
        protocol.pause("Heated to 40C. Test bounce, then resume.")
        temp_module.deactivate()
        protocol.pause("Deactivated. Test bounce, then resume.")

        temp_module.set_temperature(30)
        protocol.pause("Heated to 30C. Test bounce, then resume.")
        temp_module.deactivate()

        protocol.comment("Temperature Module disconnect recovery test complete.")

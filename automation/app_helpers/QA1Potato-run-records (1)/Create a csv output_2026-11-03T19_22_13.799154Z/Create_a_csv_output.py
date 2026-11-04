"""csv output test protocol."""
from opentrons.protocol_api import ProtocolContext
from opentrons.protocol_api.csv_context import CSVContext

metadata = {"protocolName": "Create a csv output"}
requirements = {"robotType": "Flex", "apiLevel": "2.27"}


def run(ctx: ProtocolContext) -> None:
    csv_out = ctx.create_csv(filename="test_csv_output", columns=16)
    csv_out.write_row(["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16"])

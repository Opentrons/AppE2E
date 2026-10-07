from opentrons import protocol_api

requirements = {"apiLevel": "2.28", "robotType": "Flex"}
metadata = {
    "protocolName": "Enable ODD developer tools",
    "description": "Set devtools true in /data/ODD/config.json and restart the touchscreen app.",
}


def run(protocol: protocol_api.ProtocolContext) -> None:
    # Analysis executes run() too. Leave the robot alone until a real run.
    if not protocol.is_simulating():
        import json
        import os
        import subprocess
        import uuid

        filename = "/data/ODD/config.json"
        protocol.comment("Stopping the touchscreen app")
        subprocess.run(["systemctl", "stop", "opentrons-robot-app"], check=True)

        try:
            with open(filename, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            data["devtools"] = True

            tempfile = os.path.join(os.path.dirname(filename), str(uuid.uuid4()))
            with open(tempfile, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=4)
                handle.write("\n")
            os.replace(tempfile, filename)
        except Exception:
            subprocess.run(["systemctl", "start", "opentrons-robot-app"], check=False)
            raise

        protocol.comment("Starting the touchscreen app")
        subprocess.run(["systemctl", "start", "opentrons-robot-app"], check=True)
    else:
        protocol.comment("Skipping devtools update during analysis")

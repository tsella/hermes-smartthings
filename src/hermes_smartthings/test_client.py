"""Quick sanity test for the SmartThings integration."""
import json, os, sys

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.getenv("HERMES_SMARTTHINGS_ROOT", _PROJECT_ROOT))

from .smartthings_core import get_client
from _log import get_logger

logger = get_logger("test_client")


def main():
    try:
        c = get_client()
    except RuntimeError as e:
        logger.error("Failed to create client: %s", e)
        sys.exit(1)

    logger.info("=== Locations ===")
    locs = c.list_locations()
    print(json.dumps(locs, indent=2))

    items = locs.get("items", [])
    if not items:
        logger.warning("No locations found")
        return

    loc = items[0]
    loc_id = loc["locationId"]
    loc_name = loc.get("name", "Unnamed")
    logger.info("First location: %s (%s)", loc_name, loc_id)

    logger.info("=== Devices (first 3) ===")
    devs = c.list_devices(location_id=loc_id)
    for dev in devs.get("items", [])[:3]:
        dev_id = dev["deviceId"]
        label = dev.get("label", "")
        dev_type = dev.get("deviceTypeName", "?")
        print(f"  - {label} ({dev_id}) type={dev_type}")

        status = c.get_device_status(dev_id)
        comps = status.get("components", {}).get("main", {})
        switch = comps.get("switch", {}).get("switch", {}).get("value")
        if switch is not None:
            print(f"      switch: {switch}")
        level = comps.get("switchLevel", {}).get("level", {}).get("value")
        if level is not None:
            print(f"      level: {level}")
        temp = comps.get("temperatureMeasurement", {}).get("temperature", {}).get("value")
        if temp is not None:
            print(f"      temperature: {temp}")

    logger.info("=== Rooms ===")
    rooms = c.list_rooms(location_id=loc_id)
    for room in rooms.get("items", []):
        print(f"  - {room.get('name')} ({room['roomId']})")

    logger.info("=== Modes ===")
    modes = c.list_modes(location_id=loc_id)
    for mode in modes.get("items", []):
        marker = " (current)" if mode.get("id") == modes.get("modeId") else ""
        print(f"  - {mode.get('label')} ({mode['id']}){marker}")

    logger.info("=== Current Mode ===")
    current = c.get_current_mode(location_id=loc_id)
    print(json.dumps(current, indent=2))

    logger.info("Test complete")


if __name__ == "__main__":
    main()

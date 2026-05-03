"""Quick sanity test for the SmartThings integration.

Usage:
    export SMARTTHINGS_TOKEN=pat-xxxx
    python test_client.py

Or with OAuth:
    # ensure ~/.hermes/smartthings_auth.json exists with tokens
    python test_client.py
"""
import json, os, sys

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.getenv("HERMES_SMARTTHINGS_ROOT", _PROJECT_ROOT))

from smartthings_core import get_client


def main():
    try:
        c = get_client()
    except RuntimeError as e:
        print("ERROR:", e)
        sys.exit(1)

    print("=== Locations ===")
    locs = c.list_locations()
    print(json.dumps(locs, indent=2))

    items = locs.get("items", [])
    if not items:
        print("No locations found.")
        return

    loc = items[0]
    loc_id = loc["locationId"]
    loc_name = loc.get("name", "Unnamed")
    print(f"\nFirst location: {loc_name} ({loc_id})")

    print("\n=== Devices (first 3) ===")
    devs = c.list_devices(location_id=loc_id)
    for dev in devs.get("items", [])[:3]:
        print(f"  - {dev.get('label','')} ({dev['deviceId']}) type={dev.get('deviceTypeName','?')}")
        status = c.get_device_status(dev["deviceId"])
        # Show switch/level/temperature if present
        comps = status.get("components", {}).get("main", {})
        switch = comps.get("switch", {}).get("switch", {}).get("value")
        if switch is not None:
            print(f"      switch: {switch}")
        temp = comps.get("temperatureMeasurement", {}).get("temperature", {}).get("value")
        if temp is not None:
            print(f"      temperature: {temp}")

    print("\n=== Rooms ===")
    rooms = c.list_rooms(location_id=loc_id)
    for room in rooms.get("items", []):
        print(f"  - {room.get('name')} ({room['roomId']})")

    print("\n=== Modes ===")
    modes = c.list_modes(location_id=loc_id)
    for mode in modes.get("items", []):
        marker = " (current)" if mode.get("id") == modes.get("modeId") else ""
        print(f"  - {mode.get('label')} ({mode['id']}){marker}")

    print("\n=== Current Mode ===")
    current = c.get_current_mode(location_id=loc_id)
    print(json.dumps(current, indent=2))


if __name__ == "__main__":
    main()

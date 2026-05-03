"""Quick manual test of the SmartThings client."""
import json, sys, os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    print(f"\nFirst location: {loc.get('name')} ({loc_id})")

    print("\n=== Devices ===")
    devs = c.list_devices(location_id=loc_id)
    print(json.dumps(devs, indent=2, default=str)[:4000])

    print("\n=== Rooms ===")
    rooms = c.list_rooms(location_id=loc_id)
    print(json.dumps(rooms, indent=2)[:2000])

    print("\n=== Modes ===")
    modes = c.list_modes(location_id=loc_id)
    print(json.dumps(modes, indent=2)[:2000])

    print("\n=== Current Mode ===")
    current = c.get_current_mode(location_id=loc_id)
    print(json.dumps(current, indent=2))

if __name__ == "__main__":
    main()

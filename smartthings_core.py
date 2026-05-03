"""Core SmartThings API client."""
import os, json, requests, base64, hashlib, secrets
from urllib.parse import urlencode

BASE_URL = "https://api.smartthings.com/v1"
PAT_KEY = "SMARTTHINGS_TOKEN"
OAUTH_CLIENT_ID_KEY = "SMARTTHINGS_CLIENT_ID"
OAUTH_CLIENT_SECRET_KEY = "SMARTTHINGS_CLIENT_SECRET"

class SmartThingsClient:
    def __init__(self, token: str = None, client_id: str = None, client_secret: str = None):
        self.token = token or os.getenv(PAT_KEY)
        # OAuth fields kept for future flows
        self.client_id = client_id or os.getenv(OAUTH_CLIENT_ID_KEY)
        self.client_secret = client_secret or os.getenv(OAUTH_CLIENT_SECRET_KEY)
        if not self.token:
            raise RuntimeError(f"SmartThings token not found. Set {PAT_KEY} in ~/.hermes/.env")

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def _request(self, method: str, path: str, **kwargs):
        url = f"{BASE_URL}/{path.lstrip('/')}"
        resp = requests.request(method, url, headers=self._headers(), timeout=(7, 30), **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.text else {}

    # --- Locations ---
    def list_locations(self):
        return self._request("GET", "/locations")

    def get_location(self, location_id: str):
        return self._request("GET", f"/locations/{location_id}")

    # --- Devices ---
    def list_devices(self, location_id: str = None):
        params = {}
        if location_id:
            params["locationId"] = location_id
        return self._request("GET", "/devices", params=params)

    def get_device(self, device_id: str):
        return self._request("GET", f"/devices/{device_id}")

    def send_command(self, device_id: str, command: str, args: dict = None, component: str = "main", capability: str = None):
        # Auto-resolve capability from device profile if not provided
        if not capability:
            info = self.get_device(device_id)
            cap = _infer_capability(info, command)
            if not cap:
                return {"error": f"Could not infer capability for command '{command}' on device {device_id}"}
            capability = cap
        payload = {
            "commands": [
                {
                    "component": component,
                    "capability": capability,
                    "command": command,
                    "arguments": list((args or {}).values()) if args else []
                }
            ]
        }
        return self._request("POST", f"/devices/{device_id}/commands", json=payload)

    # --- Rooms ---
    def list_rooms(self, location_id: str):
        return self._request("GET", f"/locations/{location_id}/rooms")

    # --- Modes ---
    def list_modes(self, location_id: str):
        return self._request("GET", f"/locations/{location_id}/modes")

    def get_current_mode(self, location_id: str):
        return self._request("GET", f"/locations/{location_id}/modes/current")

    def set_mode(self, location_id: str, mode_id: str):
        return self._request("PUT", f"/locations/{location_id}/modes/current", json={"modeId": mode_id})


def _infer_capability(device_info: dict, command: str) -> str | None:
    """Try to find which capability supports a given command."""
    comps = device_info.get("components", [])
    for comp in comps:
        caps = comp.get("capabilities", [])
        for cap in caps:
            version = cap.get("id", {})
            if isinstance(version, str):
                cap_id = version
            else:
                cap_id = version.get("namespace", "") + ":" + version.get("name", "") if isinstance(version, dict) else version
            # crude heuristic; rely on explicit capability in real usage
            if command.lower().replace(" ", "") in cap_id.lower().replace(":", ""):
                return cap_id
    return None


def get_client():
    return SmartThingsClient()

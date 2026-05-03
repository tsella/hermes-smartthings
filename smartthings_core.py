"""Core SmartThings API client."""
import os, requests
from urllib.parse import urlencode

from auth import get_token, start_oauth_flow

BASE_URL = "https://api.smartthings.com/v1"

# Common command -> capability mapping. Used when capability is omitted.
_COMMAND_CAP_MAP = {
    "on": "switch",
    "off": "switch",
    "setLevel": "switchLevel",
    "lock": "lock",
    "unlock": "lock",
    "setHeatingSetpoint": "thermostatHeatingSetpoint",
    "setCoolingSetpoint": "thermostatCoolingSetpoint",
    "setThermostatMode": "thermostatMode",
    "setThermostatFanMode": "thermostatFanMode",
    "setColor": "colorControl",
    "setColorTemperature": "colorTemperature",
    "open": "doorControl",
    "close": "doorControl",
    "mute": "audioMute",
    "unmute": "audioMute",
    "setVolume": "audioVolume",
    "volumeUp": "audioVolume",
    "volumeDown": "audioVolume",
    "play": "mediaPlayback",
    "pause": "mediaPlayback",
    "stop": "mediaPlayback",
}


class SmartThingsClient:
    def __init__(self, token: str | None = None):
        self._token = token or get_token()
        if not self._token:
            raise RuntimeError(
                "No SmartThings token found.\n"
                "Either set SMARTTHINGS_TOKEN in ~/.hermes/.env (PAT),\n"
                "or run OAuth setup: python -m auth (requires SMARTTHINGS_CLIENT_*)."
            )

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{BASE_URL}/{path.lstrip('/')}"
        resp = requests.request(method, url, headers=self._headers(), timeout=(7, 30), **kwargs)
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            body = {}
            try:
                body = resp.json()
            except Exception:
                pass
            return {
                "error": True,
                "status_code": resp.status_code,
                "message": body.get("error", {}).get("message") or str(e),
                "details": body.get("error", {}),
            }
        return resp.json() if resp.text else {}

    # ------------------------------------------------------------------
    # Locations
    # ------------------------------------------------------------------
    def list_locations(self) -> dict:
        return self._request("GET", "/locations")

    def get_location(self, location_id: str) -> dict:
        return self._request("GET", f"/locations/{location_id}")

    # ------------------------------------------------------------------
    # Devices
    # ------------------------------------------------------------------
    def list_devices(self, location_id: str | None = None) -> dict:
        params = {}
        if location_id:
            params["locationId"] = location_id
        return self._request("GET", "/devices", params=params)

    def get_device(self, device_id: str) -> dict:
        """Return device profile/description."""
        return self._request("GET", f"/devices/{device_id}")

    def get_device_status(self, device_id: str) -> dict:
        """Return real-time component/capability attribute values."""
        return self._request("GET", f"/devices/{device_id}/status")

    def send_command(
        self,
        device_id: str,
        command: str,
        capability: str | None = None,
        component: str = "main",
        arguments: list | None = None,
    ) -> dict:
        """Send a command to a device.

        *command* examples: on, off, setLevel, lock, unlock, setColor …
        *capability* is auto-detected for common commands.
        *arguments* is a positional list (e.g., [50] for setLevel).
        """
        resolved_cap = capability or _COMMAND_CAP_MAP.get(command)
        if not resolved_cap:
            known = ", ".join(sorted(f"{k} -> {v}" for k, v in _COMMAND_CAP_MAP.items()))
            return {
                "error": True,
                "message": (
                    f"Unknown command '{command}'. Cannot infer capability.\n"
                    f"Pass 'capability' explicitly, or use a known command.\n"
                    f"Known mappings:\n{known}"
                ),
            }

        payload = {
            "commands": [
                {
                    "component": component,
                    "capability": resolved_cap,
                    "command": command,
                    "arguments": arguments or [],
                }
            ]
        }
        return self._request("POST", f"/devices/{device_id}/commands", json=payload)

    # ------------------------------------------------------------------
    # Rooms
    # ------------------------------------------------------------------
    def list_rooms(self, location_id: str) -> dict:
        return self._request("GET", f"/locations/{location_id}/rooms")

    # ------------------------------------------------------------------
    # Modes
    # ------------------------------------------------------------------
    def list_modes(self, location_id: str) -> dict:
        return self._request("GET", f"/locations/{location_id}/modes")

    def get_current_mode(self, location_id: str) -> dict:
        return self._request("GET", f"/locations/{location_id}/modes/current")

    def set_mode(self, location_id: str, mode_id: str) -> dict:
        return self._request("PUT", f"/locations/{location_id}/modes/current", json={"modeId": mode_id})


# Convenience factory for Hermes tools
def get_client() -> SmartThingsClient:
    return SmartThingsClient()

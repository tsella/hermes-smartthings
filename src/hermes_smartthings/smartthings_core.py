"""Core SmartThings API client."""
import os
from typing import Any
import requests

from ._log import get_logger
from .auth import get_token

logger = get_logger(__name__)

BASE_URL = "https://api.smartthings.com/v1"

# Known command -> capability mappings. Used when capability is omitted.
_COMMAND_CAP_MAP: dict[str, str] = {
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
    """Low-level SmartThings REST API client with automatic auth resolution."""

    def __init__(self, token: str | None = None):
        self._token = token or get_token()
        if not self._token:
            raise RuntimeError(
                "No SmartThings token found.\n"
                "  • Set SMARTTHINGS_TOKEN in ~/.hermes/.env (PAT), or\n"
                "  • Run OAuth setup: python -c \"from auth import start_oauth_flow; ...\""
            )
        logger.info("SmartThingsClient initialized (token_source=%s)",
                    "env" if os.getenv("SMARTTHINGS_TOKEN") else "oauth_file")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        """Execute an HTTP request and return parsed JSON or an error dict."""
        url = f"{BASE_URL}/{path.lstrip('/')}"
        method_up = method.upper()
        logger.debug("%s %s", method_up, url)

        try:
            resp = requests.request(method, url, headers=self._headers(), timeout=(7, 30), **kwargs)
        except requests.RequestException as e:
            logger.error("Network error on %s %s: %s", method_up, url, e)
            return {"error": True, "status_code": 0, "message": str(e)}

        if resp.ok:
            logger.debug("%s %s → HTTP %d", method_up, url, resp.status_code)
            return resp.json() if resp.text else {}

        body: dict = {}
        try:
            body = resp.json()
        except Exception:
            pass
        msg = body.get("error", {}).get("message") or f"HTTP {resp.status_code}"
        logger.warning("API error: %s %s → HTTP %d: %s", method_up, url, resp.status_code, msg)
        return {
            "error": True,
            "status_code": resp.status_code,
            "message": msg,
            "details": body.get("error", {}),
        }

    # ------------------------------------------------------------------
    # Locations
    # ------------------------------------------------------------------
    def list_locations(self) -> dict:
        logger.info("Listing locations")
        return self._request("GET", "/locations")

    def get_location(self, location_id: str) -> dict:
        logger.info("Getting location %s", location_id)
        return self._request("GET", f"/locations/{location_id}")

    # ------------------------------------------------------------------
    # Devices
    # ------------------------------------------------------------------
    def list_devices(self, location_id: str | None = None) -> dict:
        params = {}
        if location_id:
            params["locationId"] = location_id
            logger.info("Listing devices for location %s", location_id)
        else:
            logger.info("Listing all devices")
        return self._request("GET", "/devices", params=params)

    def get_device(self, device_id: str) -> dict:
        """Return device profile (capabilities, components)."""
        logger.info("Getting device profile %s", device_id)
        return self._request("GET", f"/devices/{device_id}")

    def get_device_status(self, device_id: str) -> dict:
        """Return real-time attribute values."""
        logger.info("Getting device status %s", device_id)
        return self._request("GET", f"/devices/{device_id}/status")

    def send_command(
        self,
        device_id: str,
        command: str,
        capability: str | None = None,
        component: str = "main",
        arguments: list[Any] | None = None,
    ) -> dict:
        """Send a command to a device.

        capability is inferred from _COMMAND_CAP_MAP for common commands.
        arguments is a positional list (e.g. [50] for setLevel).
        """
        resolved_cap = capability or _COMMAND_CAP_MAP.get(command)
        if not resolved_cap:
            known = ", ".join(sorted(_COMMAND_CAP_MAP.keys()))
            logger.error("Unknown command '%s' — cannot infer capability. Known: %s", command, known)
            return {
                "error": True,
                "message": (
                    f"Unknown command '{command}'. Cannot infer capability.\n"
                    f"Pass 'capability' explicitly, or use a known command.\n"
                    f"Known: {known}"
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
        logger.info(
            "Sending command '%s' (cap=%s) to device %s [args=%s]",
            command, resolved_cap, device_id, arguments,
        )
        return self._request("POST", f"/devices/{device_id}/commands", json=payload)

    # ------------------------------------------------------------------
    # Rooms
    # ------------------------------------------------------------------
    def list_rooms(self, location_id: str) -> dict:
        logger.info("Listing rooms for location %s", location_id)
        return self._request("GET", f"/locations/{location_id}/rooms")

    # ------------------------------------------------------------------
    # Modes
    # ------------------------------------------------------------------
    def list_modes(self, location_id: str) -> dict:
        logger.info("Listing modes for location %s", location_id)
        return self._request("GET", f"/locations/{location_id}/modes")

    def get_current_mode(self, location_id: str) -> dict:
        logger.info("Getting current mode for location %s", location_id)
        return self._request("GET", f"/locations/{location_id}/modes/current")

    def set_mode(self, location_id: str, mode_id: str) -> dict:
        logger.info("Setting mode %s for location %s", mode_id, location_id)
        return self._request(
            "PUT",
            f"/locations/{location_id}/modes/current",
            json={"modeId": mode_id},
        )

    # ------------------------------------------------------------------
    # Scenes
    # ------------------------------------------------------------------
    def list_scenes(self, location_id: str | None = None) -> dict:
        params = {}
        if location_id:
            params["locationId"] = location_id
            logger.info("Listing scenes for location %s", location_id)
        else:
            logger.info("Listing all scenes")
        return self._request("GET", "/scenes", params=params)

    def execute_scene(self, scene_id: str) -> dict:
        logger.info("Executing scene %s", scene_id)
        return self._request("POST", f"/scenes/{scene_id}/execute")


def get_client() -> SmartThingsClient:
    """Factory: resolve auth and return a ready client."""
    logger.debug("Creating SmartThingsClient via get_client()")
    return SmartThingsClient()

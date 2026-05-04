"""
Unified SmartThings tool for Hermes Agent.

One interface: smartthings(action, target, value)
  list  → list devices / scenes / modes / rooms / locations
  get   → get device status (by name or ID)
  set   → send command to device (by name or ID)
  scene → execute scene (by name or ID)
  mode  → set location mode (by name or ID)

Name resolution is fuzzy — "Shade #1", "Frame 43", "OLED" all resolve automatically.
"""
import json
import logging
import os
from functools import lru_cache

from tools.registry import registry  # type: ignore[import-unresolved]

logger = logging.getLogger(__name__)

from hermes_smartthings.smartthings_core import get_client
from hermes_smartthings import config as loc_config

# ═══════════════════════════════════════════════════════════════════
# Auth detection
# ═══════════════════════════════════════════════════════════════════

AUTH_PATHS = (
    "~/.hermes/smartthings_auth.json",
    "~/.config/@smartthings/cli/credentials.json",
)


def _load_json_token(path: str) -> str | None:
    from pathlib import Path
    try:
        data = json.loads(Path(path).expanduser().read_text())
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return data.get("oauth", {}).get("access_token") or data.get("default", {}).get("accessToken")


def _has_auth() -> bool:
    if os.getenv("SMARTTHINGS_TOKEN"):
        return True
    return any(_load_json_token(p) for p in AUTH_PATHS)


# ═══════════════════════════════════════════════════════════════════
# Client helpers
# ═══════════════════════════════════════════════════════════════════


def _client():
    try:
        return get_client()
    except RuntimeError as e:
        logger.warning("Client creation failed: %s", e)
        return None


# ═══════════════════════════════════════════════════════════════════
# Fuzzy device / scene / mode / room name resolution
# ═══════════════════════════════════════════════════════════════════

@lru_cache(maxsize=8)
def _device_cache(location_id: str | None):
    """Return {lowercase_label: device_dict, ...} for fuzzy lookup."""
    c = _client()
    if not c:
        return {}
    loc = loc_config.resolve_location_id(location_id)
    data = c.list_devices(location_id=loc)
    items = data.get("items", []) if isinstance(data, dict) else []
    cache = {}
    for d in items:
        label = d.get("label", d.get("name", ""))
        cache[label.lower()] = d
        # Also index by short chunks: "Shade #1" → "shade", "#1"
        for part in label.lower().split():
            if part not in cache:
                cache[part] = d
    return cache


def _resolve_device(name: str, location_id: str | None = None) -> dict | None:
    """Fuzzy-match a device name/label and return its dict."""
    cache = _device_cache(location_id)
    if not cache:
        return None
    key = name.strip().lower()
    # Exact match
    if key in cache:
        return cache[key]
    # Contains match
    for k, v in cache.items():
        if key in k or k in key:
            return v
    return None


def _resolve_scene(name: str, location_id: str | None = None) -> str | None:
    """Return scene ID by fuzzy name match."""
    c = _client()
    if not c:
        return None
    loc = loc_config.resolve_location_id(location_id)
    data = c.list_scenes(location_id=loc)
    items = data.get("items", []) if isinstance(data, dict) else []
    key = name.strip().lower()
    for s in items:
        sname = s.get("sceneName", s.get("sceneName", "")).lower()
        sid = s.get("sceneId", s.get("sceneId", ""))
        if key == sname or key in sname or sname in key:
            return sid
    return None


def _resolve_mode(name: str, location_id: str | None = None) -> str | None:
    """Return mode ID by fuzzy name match."""
    c = _client()
    if not c:
        return None
    loc = loc_config.resolve_location_id(location_id)
    data = c.list_modes(loc)
    items = data.get("items", []) if isinstance(data, dict) else []
    key = name.strip().lower()
    for m in items:
        mname = m.get("name", "").lower()
        mid = m.get("id", m.get("modeId", ""))
        if key == mname or key in mname or mname in key:
            return mid
    return None


def _resolve_location(name: str) -> str | None:
    """Return location ID by fuzzy name match."""
    c = _client()
    if not c:
        return None
    data = c.list_locations()
    items = data.get("items", []) if isinstance(data, dict) else []
    key = name.strip().lower()
    for loc in items:
        lname = loc.get("name", "").lower()
        lid = loc.get("locationId", "")
        if key == lname or key in lname or lname in key:
            return lid
    return None


# ═══════════════════════════════════════════════════════════════════
# Action handlers
# ═══════════════════════════════════════════════════════════════════


def _action_list(what: str = "devices", location_id: str | None = None) -> dict:
    """List devices, scenes, modes, rooms, or locations."""
    c = _client()
    if not c:
        return {"error": "client unavailable"}
    loc = loc_config.resolve_location_id(location_id)

    if what in ("device", "devices"):
        if not loc:
            return {"error": "No default location. Run set location <name> first."}
        data = c.list_devices(location_id=loc)
        items = data.get("items", []) if isinstance(data, dict) else []
        return {
            "items": [
                {
                    "label": d.get("label", d.get("name", "UNKNOWN")),
                    "id": d.get("deviceId", "UNKNOWN"),
                    "type": d.get("type", "UNKNOWN"),
                    "on": _is_on(d) if "switch" in str(d.get("components", [])) else None,
                }
                for d in items
            ]
        }

    if what in ("scene", "scenes"):
        if not loc:
            return {"error": "No default location. Run set location <name> first."}
        data = c.list_scenes(location_id=loc)
        items = data.get("items", []) if isinstance(data, dict) else []
        return {"items": [{"name": s.get("sceneName", ""), "id": s.get("sceneId", "")} for s in items]}

    if what in ("mode", "modes"):
        if not loc:
            return {"error": "No default location. Run set location <name> first."}
        data = c.list_modes(loc)
        items = data.get("items", []) if isinstance(data, dict) else []
        return {"items": [{"name": m.get("name", ""), "id": m.get("id", m.get("modeId", ""))} for m in items]}

    if what in ("room", "rooms"):
        if not loc:
            return {"error": "No default location. Run set location <name> first."}
        data = c.list_rooms(loc)
        items = data.get("items", []) if isinstance(data, dict) else []
        return {"items": [{"name": r.get("name", ""), "id": r.get("roomId", "")} for r in items]}

    if what in ("location", "locations"):
        data = c.list_locations()
        items = data.get("items", []) if isinstance(data, dict) else []
        return {"items": [{"name": l.get("name", ""), "id": l.get("locationId", ""), "country": l.get("countryCode", "")} for l in items]}

    return {"error": f"Unknown list target: {what}. Try: devices, scenes, modes, rooms, locations."}


def _is_on(device_dict: dict) -> bool | None:
    """Best-effort guess if a device is on, from cached profile."""
    # We'd need status for real truth; return None for now
    return None


def _action_get(target: str, location_id: str | None = None) -> dict:
    """Get device status by name or ID."""
    c = _client()
    if not c:
        return {"error": "client unavailable"}

    # Try UUID first, then fuzzy name
    if len(target) == 36 and target.count("-") >= 3:
        device_id = target
    else:
        d = _resolve_device(target, location_id)
        if not d:
            return {"error": f"Device '{target}' not found."}
        device_id = d["deviceId"]

    status = c.get_device_status(device_id)
    profile = c.get_device(device_id)

    # Flatten the most useful attributes
    main = status.get("components", {}).get("main", {}) if isinstance(status, dict) else {}
    label = profile.get("label", profile.get("name", target)) if isinstance(profile, dict) else target

    attrs = {}
    for cap, capdata in main.items():
        if isinstance(capdata, dict):
            for attrname, attrval in capdata.items():
                if isinstance(attrval, dict) and "value" in attrval:
                    attrs[f"{cap}.{attrname}"] = attrval["value"]

    return {
        "device": label,
        "id": device_id,
        "status": attrs,
    }


def _action_set(target: str, value: str, location_id: str | None = None) -> dict:
    """Send command to device by name or ID."""
    c = _client()
    if not c:
        return {"error": "client unavailable"}

    # Try UUID first, then fuzzy name
    if len(target) == 36 and target.count("-") >= 3:
        device_id = target
    else:
        d = _resolve_device(target, location_id)
        if not d:
            return {"error": f"Device '{target}' not found."}
        device_id = d["deviceId"]

    result = c.send_command(device_id, value)
    return {
        "device": target,
        "command": value,
        "result": result,
    }


def _action_scene(target: str, location_id: str | None = None) -> dict:
    """Execute scene by name or ID."""
    c = _client()
    if not c:
        return {"error": "client unavailable"}

    if len(target) == 36 and target.count("-") >= 3:
        scene_id = target
    else:
        scene_id = _resolve_scene(target, location_id)
        if not scene_id:
            return {"error": f"Scene '{target}' not found."}

    result = c.execute_scene(scene_id)
    return {"scene": target, "result": result}


def _action_mode(target: str, location_id: str | None = None) -> dict:
    """Set location mode by name or ID."""
    c = _client()
    if not c:
        return {"error": "client unavailable"}

    loc = loc_config.resolve_location_id(location_id)
    if not loc:
        return {"error": "No default location. Run set location <name> first."}

    if len(target) == 36 and target.count("-") >= 3:
        mode_id = target
    else:
        mode_id = _resolve_mode(target, location_id)
        if not mode_id:
            return {"error": f"Mode '{target}' not found."}

    result = c.set_mode(loc, mode_id)
    return {"mode": target, "result": result}


def _action_location(name: str) -> dict:
    """Set default location by name."""
    loc_id = _resolve_location(name)
    if not loc_id:
        return {"error": f"Location '{name}' not found."}
    loc_config.set_default_location(loc_id)
    _device_cache.cache_clear()  # invalidate cache
    return {"default_location": name, "id": loc_id}


# ═══════════════════════════════════════════════════════════════════
# Main unified entry point
# ═══════════════════════════════════════════════════════════════════


def smartthings(action: str, target: str = "", value: str = "", location_id: str = "") -> str:
    """
    Unified SmartThings control.

    Actions:
      list  → target=device|scene|mode|room|location
      get   → target=<device name or ID>
      set   → target=<device name or ID>, value=<command>
      scene → target=<scene name or ID>
      mode  → target=<mode name or ID>
      location → target=<location name>
    """
    action = action.strip().lower()
    target = target.strip()
    value = value.strip()
    loc = location_id.strip() or None

    if action == "list":
        result = _action_list(what=target or "devices", location_id=loc)
    elif action == "get":
        result = _action_get(target=target, location_id=loc)
    elif action == "set":
        result = _action_set(target=target, value=value, location_id=loc)
    elif action == "scene":
        result = _action_scene(target=target, location_id=loc)
    elif action == "mode":
        result = _action_mode(target=target, location_id=loc)
    elif action == "location":
        result = _action_location(name=target)
    else:
        result = {"error": f"Unknown action '{action}'. Try: list, get, set, scene, mode, location."}

    return json.dumps(result, indent=2, default=str)


# ═══════════════════════════════════════════════════════════════════
# Hermes registration — ONE tool replaces 13
# ═══════════════════════════════════════════════════════════════════

_SCHEMA = {
    "name": "smartthings",
    "description": (
        "Unified SmartThings control. Single interface for list/get/set/scene/mode.\n"
        "Examples:\n"
        "  smartthings('list', 'devices')\n"
        "  smartthings('get', 'Shade #1')\n"
        "  smartthings('set', 'Shade #1', 'close')\n"
        "  smartthings('scene', 'Movie Night')\n"
        "  smartthings('mode', 'Away')\n"
        "  smartthings('location', '35E38St')"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "get", "set", "scene", "mode", "location"],
                "description": "What to do: list, get, set, scene, mode, or location",
            },
            "target": {
                "type": "string",
                "description": "Device name/ID, scene name, mode name, or list target (devices/scenes/modes/rooms/locations).",
            },
            "value": {
                "type": "string",
                "description": "Command value for 'set' action (e.g., on, off, close, setLevel).",
            },
            "location_id": {
                "type": "string",
                "description": "Optional location UUID override.",
            },
        },
        "required": ["action"],
    },
}


def _handler(args: dict, **kwargs) -> str:
    return smartthings(
        action=args.get("action", ""),
        target=args.get("target", ""),
        value=args.get("value", ""),
        location_id=args.get("location_id", ""),
    )


registry.register(
    name="smartthings",
    toolset="smartthings",
    schema=_SCHEMA,
    handler=_handler,
    check_fn=_has_auth,
)

logger.info("SmartThings unified tool registered")

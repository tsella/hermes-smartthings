"""
Unified SmartThings tool for Hermes Agent.

One interface handles everything: scene preflight, semantic command dispatch,
plural / group targets, and fuzzy name lookup. 13 tools collapsed into one.

    smartthings(action, target, value)

Actions:
  list  → target=device|scene|mode|room|location  (plural-aware)
  get   → target=<device name or ID>
  set   → target=<device(s) name or ID>, value=<command>
          (preflight: checks for matching scene first)
  scene → target=<scene name or ID>
  mode  → target=<mode name or ID>
  location → target=<location name>

Examples:
    smartthings("set", "shades", "open")
    smartthings("set", "Shade #1", "close")
    smartthings("set", "Frame 43", "on")
    smartthings("set", "all tvs", "off")
    smartthings("scene", "Movie Night")
"""
import json
import logging
import os
import re
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
# Device cache — indexed multiple ways for fast lookup
# ═══════════════════════════════════════════════════════════════════

class _DeviceIndex:
    """Indexed view of all devices: by label, by capability, by category."""

    def __init__(self, location_id: str | None = None):
        self.location_id = location_id
        self.devices: list[dict] = []          # deduplicated, canonical device list
        self.by_label: dict[str, dict] = {}
        self.by_capability: dict[str, list[dict]] = {}
        self.by_category: dict[str, list[dict]] = {}
        self._location = loc_config.resolve_location_id(location_id)
        self._refresh()

    def _refresh(self):
        c = _client()
        if not c:
            return
        data = c.list_devices(location_id=self._location)
        items = data.get("items", []) if isinstance(data, dict) else []

        self.devices.clear()
        self.by_label.clear()
        self.by_capability.clear()
        self.by_category.clear()

        # Deduplicate while preserving order
        seen_ids = set()
        for d in items:
            dev_id = d.get("deviceId")
            if dev_id and dev_id in seen_ids:
                continue
            if dev_id:
                seen_ids.add(dev_id)
            self.devices.append(d)

            label = d.get("label", d.get("name", ""))
            self.by_label[label.lower()] = d
            self.by_label[label.lower().replace(" ", "")] = d
            for part in label.lower().split():
                self.by_label.setdefault(part, d)

            # Index by capability
            for comp in d.get("components", []):
                for cap in comp.get("capabilities", []):
                    cap_id = cap.get("id", "")
                    self.by_capability.setdefault(cap_id, []).append(d)

                # Index by category
                for cat in comp.get("categories", []):
                    cat_name = cat.get("name", "").lower()
                    self.by_category.setdefault(cat_name, []).append(d)

    def devices_with_capability(self, capability: str) -> list[dict]:
        return list(self.by_capability.get(capability, []))

    def devices_by_category(self, category: str) -> list[dict]:
        return list(self.by_category.get(category.lower(), []))

    def resolve(self, query: str) -> dict | None:
        """Fuzzy-match a single device label."""
        q = query.strip().lower()
        if q in self.by_label:
            return self.by_label[q]
        for k, v in self.by_label.items():
            if q in k or k in q:
                return v
        return None

    def resolve_group(self, query: str) -> list[dict]:
        """Resolve plural / group queries like 'shades', 'tvs', 'all shades'."""
        q = query.strip().lower()

        # Strip 'all ' prefix
        if q.startswith("all "):
            q = q[4:].strip()

        # Direct capability match
        capability_map = {
            "shades": "windowShade", "shade": "windowShade",
            "blinds": "windowShade", "blind": "windowShade",
            "lights": "switch", "light": "switch",
            "switches": "switch", "switch": "switch",
            "doors": "lock", "door": "lock",
            "locks": "lock", "lock": "lock",
            "tv": "switch", "tvs": "switch",
            "televisions": "switch", "television": "switch",
            "speakers": "audioVolume", "speaker": "audioVolume",
            "projectors": "switch", "projector": "switch",
        }

        cap = capability_map.get(q)
        if cap:
            devs = self.devices_with_capability(cap)
            # For TVs / projectors, also filter by category to avoid mixing with regular switches
            if q in ("tv", "tvs", "television", "televisions"):
                tv_by_cat = self.devices_by_category("television")
                return list({d["deviceId"]: d for d in tv_by_cat}.values()) or devs
            if q in ("projector", "projectors"):
                proj_by_cat = self.devices_by_category("projector")
                return list({d["deviceId"]: d for d in proj_by_cat}.values()) or devs
            return devs

        return []


@lru_cache(maxsize=4)
def _get_index(location_id: str | None = None):
    return _DeviceIndex(location_id)


def _invalidate_cache():
    _get_index.cache_clear()


# ═══════════════════════════════════════════════════════════════════
# Scene / mode / location resolution
# ═══════════════════════════════════════════════════════════════════


def _resolve_scene(name: str, location_id: str | None = None) -> str | None:
    c = _client()
    if not c:
        return None
    loc = loc_config.resolve_location_id(location_id)
    data = c.list_scenes(location_id=loc)
    items = data.get("items", []) if isinstance(data, dict) else []
    key = name.strip().lower()
    for s in items:
        sname = s.get("sceneName", "").lower()
        sid = s.get("sceneId", "")
        if key == sname or key in sname or sname in key:
            return sid
    return None


def _resolve_mode(name: str, location_id: str | None = None) -> str | None:
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
# Scene preflight — check if user intent matches a named scene
# ═══════════════════════════════════════════════════════════════════


def _scene_preflight(target: str, value: str, location_id: str | None = None) -> str | None:
    """
    Returns scene ID if a named scene matches the user's intent.
    e.g. target='shades', value='open' → scene 'Window Shade: Open'
    """
    c = _client()
    if not c:
        return None
    loc = loc_config.resolve_location_id(location_id)
    data = c.list_scenes(location_id=loc)
    items = data.get("items", []) if isinstance(data, dict) else []

    t = target.strip().lower()
    v = value.strip().lower()

    for s in items:
        sname = s.get("sceneName", "").lower()
        sid = s.get("sceneId", "")
        # Match: scene name contains the value (open/close) AND the target keyword
        if v in sname:
            # Check if target keyword (or a synonym) is in scene name
            keywords = [t]
            if t in ("shades", "shade"):
                keywords = ["shade", "shades", "window shade", "window"]
            for kw in keywords:
                if kw in sname:
                    logger.info("Scene preflight match: '%s' for '%s %s'", sname, t, v)
                    return sid
    return None


# ═══════════════════════════════════════════════════════════════════
# Semantic command dispatch — value + device capabilities → command + capability
# ═══════════════════════════════════════════════════════════════════


def _resolve_semantic_command(value: str, device: dict) -> tuple[str, str]:
    """
    Given a user value ('open', 'close', 'on', 'off') and a device dict,
    return (command, capability) appropriate for that device type.

    Raises ValueError if no applicable capability found.
    """
    v = value.strip().lower()

    # Gather all capability IDs from the device
    caps = set()
    for comp in device.get("components", []):
        for cap in comp.get("capabilities", []):
            caps.add(cap.get("id", ""))

    # ━━ open ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if v == "open":
        if "windowShade" in caps:
            return "open", "windowShade"
        if "doorControl" in caps:
            return "open", "doorControl"
        if "switch" in caps:
            return "on", "switch"
        raise ValueError(f"Device has no openable capability. Has: {caps}")

    # ━━ close ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if v == "close":
        if "windowShade" in caps:
            return "close", "windowShade"
        if "switch" in caps:
            return "off", "switch"
        if "lock" in caps:
            return "lock", "lock"
        raise ValueError(f"Device has no closable capability. Has: {caps}")

    # ━━ on ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if v == "on":
        if "switch" in caps:
            return "on", "switch"
        if "thermostatMode" in caps:
            return "auto", "thermostatMode"
        raise ValueError(f"Device has no 'on' capability. Has: {caps}")

    # ━━ off ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if v == "off":
        if "switch" in caps:
            return "off", "switch"
        if "thermostatMode" in caps:
            return "off", "thermostatMode"
        raise ValueError(f"Device has no 'off' capability. Has: {caps}")

    # ━━ pause / play / stop ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if v in ("pause", "play", "stop"):
        if "mediaPlayback" in caps:
            return v, "mediaPlayback"
        if "switch" in caps:
            # Fallback: treat as on/off for non-media devices
            return "off" if v == "stop" else "on", "switch"
        raise ValueError(f"Device has no media capability. Has: {caps}")

    # ━━ volume commands ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if v in ("mute", "unmute"):
        if "audioMute" in caps:
            return v, "audioMute"
        if "audioVolume" in caps:
            return v, "audioVolume"  # fallback
        raise ValueError(f"Device has no mute capability. Has: {caps}")

    if v in ("volumedown", "volume_down"):
        if "audioVolume" in caps:
            return "volumeDown", "audioVolume"
        raise ValueError(f"Device has no audioVolume capability. Has: {caps}")

    if v in ("volumeup", "volume_up"):
        if "audioVolume" in caps:
            return "volumeUp", "audioVolume"
        raise ValueError(f"Device has no audioVolume capability. Has: {caps}")

    # ━━ lock / unlock ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if v == "lock":
        if "lock" in caps:
            return "lock", "lock"
        raise ValueError(f"Device has no lock capability. Has: {caps}")

    if v == "unlock":
        if "lock" in caps:
            return "unlock", "lock"
        raise ValueError(f"Device has no lock capability. Has: {caps}")

    # ━━ unknown — pass through (let core validate) ━━━━━━━━━━━━━━━━
    logger.warning("Unrecognized value '%s' — passing through. Device caps: %s", v, caps)
    return v, None


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
        idx = _get_index(loc)
        return {
            "items": [
                {
                    "label": d.get("label", d.get("name", "UNKNOWN")),
                    "id": d.get("deviceId", "UNKNOWN"),
                    "type": d.get("type", "UNKNOWN"),
                }
                for d in sorted(idx.devices, key=lambda x: x.get("label", ""))
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


def _action_get(target: str, location_id: str | None = None) -> dict:
    """Get device status by name or ID."""
    c = _client()
    if not c:
        return {"error": "client unavailable"}

    # Try UUID first
    if len(target) == 36 and target.count("-") >= 3:
        device_id = target
    else:
        idx = _get_index(location_id)
        d = idx.resolve(target)
        if not d:
            return {"error": f"Device '{target}' not found."}
        device_id = d["deviceId"]

    status = c.get_device_status(device_id)
    profile = c.get_device(device_id)

    main = status.get("components", {}).get("main", {}) if isinstance(status, dict) else {}
    label = profile.get("label", profile.get("name", target)) if isinstance(profile, dict) else target

    attrs = {}
    for cap, capdata in main.items():
        if isinstance(capdata, dict):
            for attrname, attrval in capdata.items():
                if isinstance(attrval, dict) and "value" in attrval:
                    attrs[f"{cap}.{attrname}"] = attrval["value"]

    return {"device": label, "id": device_id, "status": attrs}


def _action_set(target: str, value: str, location_id: str | None = None) -> dict:
    """Send command to device(s) by name or ID. Scene preflight + semantic dispatch."""
    c = _client()
    if not c:
        return {"error": "client unavailable"}

    # ── Scene preflight ──────────────────────────────────────────
    scene_id = _scene_preflight(target, value, location_id)
    if scene_id:
        result = c.execute_scene(scene_id)
        return {
            "action": "scene_executed",
            "scene": target,
            "value": value,
            "result": result,
        }

    # ── Resolve target(s) ────────────────────────────────────────
    devices: list[dict] = []
    is_group = False

    # Try UUID first
    if len(target) == 36 and target.count("-") >= 3:
        devices = [{"deviceId": target}]
    else:
        idx = _get_index(location_id)
        # Try group / plural first
        group_devs = idx.resolve_group(target)
        if group_devs:
            devices = group_devs
            is_group = True
        else:
            # Single device
            d = idx.resolve(target)
            if d:
                devices = [d]
            else:
                return {"error": f"Device or group '{target}' not found."}

    # ── Semantic dispatch per device ─────────────────────────────
    results = []
    errors = []
    for d in devices:
        label = d.get("label", d.get("name", d.get("deviceId", "Unknown")))
        try:
            command, capability = _resolve_semantic_command(value, d)
            if capability:
                result = c.send_command(d["deviceId"], command, capability=capability)
            else:
                result = c.send_command(d["deviceId"], command)
            results.append({
                "device": label,
                "command": command,
                "capability": capability,
                "result": result,
            })
        except ValueError as e:
            errors.append({"device": label, "error": str(e)})

    return {
        "action": "commands_sent",
        "target": target,
        "value": value,
        "devices_affected": len(results),
        "results": results,
        "errors": errors,
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
    _invalidate_cache()
    return {"default_location": name, "id": loc_id}


# ═══════════════════════════════════════════════════════════════════
# Main unified entry point
# ═══════════════════════════════════════════════════════════════════


def smartthings(action: str, target: str = "", value: str = "", location_id: str = "") -> str:
    """
    Unified SmartThings control with scene preflight and semantic dispatch.

    Actions:
      list  → target=device|scene|mode|room|location
      get   → target=<device name or ID>
      set   → target=<device(s) name or ID>, value=<command>
                (scene preflight first, then semantic device dispatch)
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
# Hermes registration — ONE tool
# ═══════════════════════════════════════════════════════════════════

_SCHEMA = {
    "name": "smartthings",
    "description": (
        "Unified SmartThings control. Scene preflight + semantic command dispatch.\n"
        "Examples:\n"
        "  smartthings('list', 'devices')\n"
        "  smartthings('get', 'Shade #1')\n"
        "  smartthings('set', 'shades', 'open')          # scene preflight, then semantic dispatch\n"
        "  smartthings('set', 'Frame 43', 'on')         # 'on' → switch.on for TV\n"
        "  smartthings('set', 'all tvs', 'off')          # group target\n"
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
                "description": "Device name/ID, group (shades/tvs), scene name, or list target.",
            },
            "value": {
                "type": "string",
                "description": "Command value for 'set' action (e.g., on, off, close, open).",
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

logger.info("SmartThings unified tool registered (v2: scene preflight + semantic dispatch)")

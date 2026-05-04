"""
Hermes tool registration for Samsung SmartThings.

Requires package installation:
  pip install -e ~/projects/hermes-smartthings
"""
import json
import logging
from functools import wraps

logger = logging.getLogger(__name__)

from tools.registry import registry  # type: ignore[import-unresolved]

from hermes_smartthings.smartthings_core import get_client, SmartThingsClient
from hermes_smartthings.auth import get_token


# ── Auth helper ────────────────────────────────────────────────────


def _load_json_token(path: str) -> str | None:
    import json
    from pathlib import Path
    p = Path(path).expanduser()
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
        return data.get("oauth", {}).get("access_token") or data.get("default", {}).get("accessToken")
    except Exception:
        return None


def _has_auth() -> bool:
    import os
    if os.getenv("SMARTTHINGS_TOKEN"):
        return True
    if _load_json_token("~/.hermes/smartthings_auth.json"):
        return True
    if _load_json_token("~/.config/@smartthings/cli/credentials.json"):
        return True
    return False


# ── Client helper ──────────────────────────────────────────────────


def _client() -> SmartThingsClient | None:
    try:
        return get_client()
    except RuntimeError as e:
        logger.warning("Client creation failed: %s", e)
        return None


def _tool(fn):
    """Decorator: resolve client, handle auth errors, log entry/exit."""
    @wraps(fn)
    def wrapper(*args, task_id: str | None = None, **kwargs):
        name = fn.__name__
        logger.info("[tool] %s", name)
        c = _client()
        if not c:
            return json.dumps({"error": True, "message": f"{name}: SmartThings client unavailable."}, indent=2)
        return json.dumps(fn(c, *args, **kwargs), indent=2)
    return wrapper


# ── Tool implementations ───────────────────────────────────────────

@_tool
def smartthings_list_locations(c):
    return c.list_locations()


@_tool
def smartthings_list_devices(c, location_id: str | None = None):
    return c.list_devices(location_id=location_id)


@_tool
def smartthings_get_device(c, device_id: str):
    return c.get_device(device_id)


@_tool
def smartthings_get_device_status(c, device_id: str):
    return c.get_device_status(device_id)


@_tool
def smartthings_send_command(c, device_id: str, command: str, capability: str | None = None,
                             component: str = "main", arguments: list | None = None):
    return c.send_command(device_id, command, capability=capability,
                          component=component, arguments=arguments or [])


@_tool
def smartthings_list_rooms(c, location_id: str):
    return c.list_rooms(location_id)


@_tool
def smartthings_list_modes(c, location_id: str):
    return c.list_modes(location_id)


@_tool
def smartthings_get_current_mode(c, location_id: str):
    return c.get_current_mode(location_id)


@_tool
def smartthings_set_mode(c, location_id: str, mode_id: str):
    return c.set_mode(location_id, mode_id)


# ── Hermes registry boilerplate ────────────────────────────────────

_TOOL_SPECS = [
    ("smartthings_list_locations", "List all SmartThings locations.", {}, []),
    ("smartthings_list_devices", "List devices. Optionally filter by location_id.",
     {"location_id": {"type": "string", "description": "Location UUID (optional)"}}, []),
    ("smartthings_get_device", "Get full device status, capabilities, and components.",
     {"device_id": {"type": "string", "description": "Device UUID"}}, ["device_id"]),
    ("smartthings_get_device_status", "Get real-time attribute values (temperature, switch, lock, etc.).",
     {"device_id": {"type": "string", "description": "Device UUID"}}, ["device_id"]),
    ("smartthings_send_command", "Send a command. Common: on, off, setLevel, lock, setColor. Capability auto-inferred.",
     {
         "device_id": {"type": "string", "description": "Device UUID"},
         "command": {"type": "string", "description": "Command name (e.g. on, off, setLevel)"},
         "capability": {"type": "string", "description": "Optional capability ID (e.g. switch, switchLevel)"},
         "component": {"type": "string", "description": "Component, usually main", "default": "main"},
         "arguments": {"type": "array", "description": "Positional args list (e.g. [50])"},
     }, ["device_id", "command"]),
    ("smartthings_list_rooms", "List rooms in a location.",
     {"location_id": {"type": "string", "description": "Location UUID"}}, ["location_id"]),
    ("smartthings_list_modes", "List modes (Home, Away, Night, etc.).",
     {"location_id": {"type": "string", "description": "Location UUID"}}, ["location_id"]),
    ("smartthings_get_current_mode", "Get the currently active mode.",
     {"location_id": {"type": "string", "description": "Location UUID"}}, ["location_id"]),
    ("smartthings_set_mode", "Change the current mode.",
     {
         "location_id": {"type": "string", "description": "Location UUID"},
         "mode_id": {"type": "string", "description": "Mode UUID"},
     }, ["location_id", "mode_id"]),
]


for _name, _desc, _params, _required in _TOOL_SPECS:
    _schema = {
        "name": _name,
        "description": _desc,
        "parameters": {"type": "object", "properties": _params, "required": _required},
    }
    registry.register(
        name=_name,
        toolset="smartthings",
        schema=_schema,
        handler=lambda args, _n=_name, **kw: globals()[_n](**args, task_id=kw.get("task_id")),
        check_fn=_has_auth,
    )
    logger.debug("Registered tool: %s", _name)

logger.info("SmartThings toolset loaded (%d tools)", len(_TOOL_SPECS))

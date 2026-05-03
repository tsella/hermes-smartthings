"""
Hermes tool registration for Samsung SmartThings.

Symlink into Hermes:
  ln -s "$PROJECT_ROOT/tools/smartthings_tool.py" "$HOME/.hermes/hermes-agent/tools/smartthings_tool.py"

Then add to PYTHONPATH so auth.py and smartthings_core.py resolve:
  export HERMES_SMARTTHINGS_ROOT=/path/to/hermes-smartthings
"""
import json, os, sys
from pathlib import Path

# ── Resolve imports ────────────────────────────────────────────────
# When running from a symlink in hermes-agent/tools/, _PROJECT_ROOT points
# to wherever the symlink target lives. We inject that onto PYTHONPATH so
# sibling modules (auth.py, smartthings_core.py) import cleanly.
_THIS = Path(__file__).resolve()
_PROJECT_ROOT = _THIS.parent.parent
sys.path.insert(0, os.getenv("HERMES_SMARTTHINGS_ROOT", str(_PROJECT_ROOT)))

try:
    from smartthings_core import get_client, SmartThingsClient
    _OK = True
except Exception:
    SmartThingsClient = None
    _OK = False

# registry import must survive standalone import (e.g. `python smartthings_tool.py`)
# When symlinked into hermes-agent/tools/, the package root is in sys.path.
from tools.registry import registry  # type: ignore[import-unresolved]


# ── Auth probe (determines toolset availability) ───────────────────

def _has_auth() -> bool:
    """Return True if any auth source is present (PAT env or saved OAuth)."""
    if os.getenv("SMARTTHINGS_TOKEN"):
        return True
    token_file = Path.home() / ".hermes" / "smartthings_auth.json"
    if token_file.exists():
        try:
            data = json.loads(token_file.read_text())
            return bool(data.get("oauth", {}).get("access_token"))
        except Exception:
            return False
    return False


# ── Client helper ──────────────────────────────────────────────────

def _client() -> SmartThingsClient | None:
    if not _OK:
        return None
    try:
        return get_client()
    except RuntimeError:
        return None


def _err(msg: str) -> str:
    return json.dumps({"error": True, "message": msg}, indent=2)


# ── Tool handlers ──────────────────────────────────────────────────

def smartthings_list_locations(task_id: str | None = None) -> str:
    c = _client()
    if not c:
        return _err("SmartThings client unavailable. No valid token found.")
    return json.dumps(c.list_locations(), indent=2)


def smartthings_list_devices(location_id: str | None = None, task_id: str | None = None) -> str:
    c = _client()
    if not c:
        return _err("SmartThings client unavailable.")
    return json.dumps(c.list_devices(location_id=location_id), indent=2)


def smartthings_get_device(device_id: str, task_id: str | None = None) -> str:
    c = _client()
    if not c:
        return _err("SmartThings client unavailable.")
    return json.dumps(c.get_device(device_id), indent=2)


def smartthings_get_device_status(device_id: str, task_id: str | None = None) -> str:
    c = _client()
    if not c:
        return _err("SmartThings client unavailable.")
    return json.dumps(c.get_device_status(device_id), indent=2)


def smartthings_send_command(
    device_id: str,
    command: str,
    capability: str | None = None,
    component: str = "main",
    arguments: list | None = None,
    task_id: str | None = None,
) -> str:
    c = _client()
    if not c:
        return _err("SmartThings client unavailable.")
    return json.dumps(
        c.send_command(
            device_id, command,
            capability=capability, component=component, arguments=arguments or []
        ),
        indent=2,
    )


def smartthings_list_rooms(location_id: str, task_id: str | None = None) -> str:
    c = _client()
    if not c:
        return _err("SmartThings client unavailable.")
    return json.dumps(c.list_rooms(location_id), indent=2)


def smartthings_list_modes(location_id: str, task_id: str | None = None) -> str:
    c = _client()
    if not c:
        return _err("SmartThings client unavailable.")
    return json.dumps(c.list_modes(location_id), indent=2)


def smartthings_get_current_mode(location_id: str, task_id: str | None = None) -> str:
    c = _client()
    if not c:
        return _err("SmartThings client unavailable.")
    return json.dumps(c.get_current_mode(location_id), indent=2)


def smartthings_set_mode(location_id: str, mode_id: str, task_id: str | None = None) -> str:
    c = _client()
    if not c:
        return _err("SmartThings client unavailable.")
    return json.dumps(c.set_mode(location_id, mode_id), indent=2)


# ── Hermes registry boilerplate ────────────────────────────────────

_TOOL_SPECS = [
    ("smartthings_list_locations", "List all SmartThings locations.", {}, []),
    ("smartthings_list_devices", "List devices. Optionally filter by location_id.",
     {"location_id": {"type": "string", "description": "Location UUID (optional)"}}, []),
    ("smartthings_get_device", "Get full device status, capabilities, and components.",
     {"device_id": {"type": "string", "description": "Device UUID"}}, ["device_id"]),
    ("smartthings_get_device_status", "Get real-time attribute values (temperature, switch, lock, etc.).",
     {"device_id": {"type": "string", "description": "Device UUID"}}, ["device_id"]),
    ("smartthings_send_command", "Send a command to a device. Common: on, off, setLevel, lock, setColor.",
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
        requires_env=["SMARTTHINGS_TOKEN"],  # at minimum this makes toolset visible in listings
    )

"""
Hermes tool registration for Samsung SmartThings.

tools/smartthings_tool.py

Place this file in ~/.hermes/hermes-agent/tools/
or symlink it from the project repo. Restart Hermes after.
"""
import json, os, sys
# Ensure core module is importable if it's on PYTHONPATH or in project root
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.dirname(os.path.abspath(__file__)) in sys.path:
    # Running from hermes-agent/tools/ — add project root to path if core lives there
    pass
# Prefer imports relative to project root or via PYTHONPATH
from tools.registry import registry

# Try local import first (if running from within project), then absolute
_succeed = False
try:
    from smartthings_core import get_client, SmartThingsClient
    _succeed = True
except ImportError:
    pass

if not _succeed:
    # Allow user to set project root via env var
    _proj = os.getenv("HERMES_SMARTTHINGS_ROOT")
    if _proj:
        sys.path.insert(0, _proj)
    try:
        from smartthings_core import get_client, SmartThingsClient
        _succeed = True
    except ImportError:
        pass

if not _succeed:
    SmartThingsClient = None

def _ensure_client():
    if SmartThingsClient is None:
        return None
    try:
        return get_client()
    except RuntimeError:
        return None


def smartthings_list_locations(task_id: str | None = None) -> str:
    """List all SmartThings locations."""
    c = _ensure_client()
    if not c:
        return json.dumps({"error": "SmartThings client unavailable. Set SMARTTHINGS_TOKEN in .env and ensure smartthings_core.py is on PYTHONPATH."})
    return json.dumps(c.list_locations(), indent=2)


def smartthings_list_devices(location_id: str | None = None, task_id: str | None = None) -> str:
    """List devices. Optionally filter by location_id."""
    c = _ensure_client()
    if not c:
        return json.dumps({"error": "SmartThings client unavailable."})
    return json.dumps(c.list_devices(location_id=location_id), indent=2)


def smartthings_get_device(device_id: str, task_id: str | None = None) -> str:
    """Get full device status, capabilities, and components."""
    c = _ensure_client()
    if not c:
        return json.dumps({"error": "SmartThings client unavailable."})
    return json.dumps(c.get_device(device_id), indent=2)


def smartthings_send_command(device_id: str, command: str, capability: str | None = None, component: str = "main", arguments: dict | None = None, task_id: str | None = None) -> str:
    """Send a command to a device. Common commands: on, off, setLevel, lock, unlock, setColor.
    capability is inferred automatically for common commands if omitted.
    arguments should be a dict mapping arg name -> value (e.g. {"level": 50} for setLevel).
    """
    c = _ensure_client()
    if not c:
        return json.dumps({"error": "SmartThings client unavailable."})
    return json.dumps(c.send_command(device_id, command, args=(arguments or {}), component=component, capability=capability), indent=2)


def smartthings_list_rooms(location_id: str, task_id: str | None = None) -> str:
    """List rooms in a location."""
    c = _ensure_client()
    if not c:
        return json.dumps({"error": "SmartThings client unavailable."})
    return json.dumps(c.list_rooms(location_id), indent=2)


def smartthings_list_modes(location_id: str, task_id: str | None = None) -> str:
    """List modes (Home, Away, etc.) for a location."""
    c = _ensure_client()
    if not c:
        return json.dumps({"error": "SmartThings client unavailable."})
    return json.dumps(c.list_modes(location_id), indent=2)


def smartthings_get_current_mode(location_id: str, task_id: str | None = None) -> str:
    """Get the current mode for a location."""
    c = _ensure_client()
    if not c:
        return json.dumps({"error": "SmartThings client unavailable."})
    return json.dumps(c.get_current_mode(location_id), indent=2)


def smartthings_set_mode(location_id: str, mode_id: str, task_id: str | None = None) -> str:
    """Change the current mode for a location."""
    c = _ensure_client()
    if not c:
        return json.dumps({"error": "SmartThings client unavailable."})
    return json.dumps(c.set_mode(location_id, mode_id), indent=2)


def _check_requirements() -> bool:
    return os.getenv("SMARTTHINGS_TOKEN") is not None and SmartThingsClient is not None


# Register with Hermes
registry.register(
    name="smartthings_list_locations",
    toolset="smartthings",
    schema={
        "name": "smartthings_list_locations",
        "description": "List all SmartThings locations in the account.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    handler=lambda args, **kw: smartthings_list_locations(task_id=kw.get("task_id")),
    check_fn=_check_requirements,
    requires_env=["SMARTTHINGS_TOKEN"]
)

registry.register(
    name="smartthings_list_devices",
    toolset="smartthings",
    schema={
        "name": "smartthings_list_devices",
        "description": "List devices in SmartThings. Optionally filter by location_id.",
        "parameters": {
            "type": "object",
            "properties": {"location_id": {"type": "string", "description": "Location UUID (optional)"}},
            "required": []
        }
    },
    handler=lambda args, **kw: smartthings_list_devices(location_id=args.get("location_id"), task_id=kw.get("task_id")),
    check_fn=_check_requirements,
    requires_env=["SMARTTHINGS_TOKEN"]
)

registry.register(
    name="smartthings_get_device",
    toolset="smartthings",
    schema={
        "name": "smartthings_get_device",
        "description": "Get full status, capabilities, and components of a SmartThings device.",
        "parameters": {
            "type": "object",
            "properties": {"device_id": {"type": "string", "description": "Device UUID"}},
            "required": ["device_id"]
        }
    },
    handler=lambda args, **kw: smartthings_get_device(device_id=args.get("device_id"), task_id=kw.get("task_id")),
    check_fn=_check_requirements,
    requires_env=["SMARTTHINGS_TOKEN"]
)

registry.register(
    name="smartthings_send_command",
    toolset="smartthings",
    schema={
        "name": "smartthings_send_command",
        "description": "Send a command to a SmartThings device. Common commands: on, off, setLevel, lock, unlock. Capability is inferred automatically for common commands if omitted. Use smartthings_get_device to inspect capabilities/commands if unsure.",
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "Device UUID"},
                "command": {"type": "string", "description": "Command name (e.g. on, off, setLevel, lock, setColor)"},
                "capability": {"type": "string", "description": "Optional capability ID (e.g. switch, switchLevel, lock)"},
                "component": {"type": "string", "description": "Component ID, usually 'main'", "default": "main"},
                "arguments": {"type": "object", "description": "Command arguments as key-value dict (e.g. {\"level\": 50})"}
            },
            "required": ["device_id", "command"]
        }
    },
    handler=lambda args, **kw: smartthings_send_command(
        device_id=args.get("device_id"), command=args.get("command"),
        capability=args.get("capability"), component=args.get("component", "main"),
        arguments=args.get("arguments"), task_id=kw.get("task_id")
    ),
    check_fn=_check_requirements,
    requires_env=["SMARTTHINGS_TOKEN"]
)

registry.register(
    name="smartthings_list_rooms",
    toolset="smartthings",
    schema={
        "name": "smartthings_list_rooms",
        "description": "List rooms within a SmartThings location.",
        "parameters": {
            "type": "object",
            "properties": {"location_id": {"type": "string", "description": "Location UUID"}},
            "required": ["location_id"]
        }
    },
    handler=lambda args, **kw: smartthings_list_rooms(location_id=args.get("location_id"), task_id=kw.get("task_id")),
    check_fn=_check_requirements,
    requires_env=["SMARTTHINGS_TOKEN"]
)

registry.register(
    name="smartthings_list_modes",
    toolset="smartthings",
    schema={
        "name": "smartthings_list_modes",
        "description": "List modes (Home, Away, Night, etc.) for a location.",
        "parameters": {
            "type": "object",
            "properties": {"location_id": {"type": "string", "description": "Location UUID"}},
            "required": ["location_id"]
        }
    },
    handler=lambda args, **kw: smartthings_list_modes(location_id=args.get("location_id"), task_id=kw.get("task_id")),
    check_fn=_check_requirements,
    requires_env=["SMARTTHINGS_TOKEN"]
)

registry.register(
    name="smartthings_get_current_mode",
    toolset="smartthings",
    schema={
        "name": "smartthings_get_current_mode",
        "description": "Get the currently active mode for a location.",
        "parameters": {
            "type": "object",
            "properties": {"location_id": {"type": "string", "description": "Location UUID"}},
            "required": ["location_id"]
        }
    },
    handler=lambda args, **kw: smartthings_get_current_mode(location_id=args.get("location_id"), task_id=kw.get("task_id")),
    check_fn=_check_requirements,
    requires_env=["SMARTTHINGS_TOKEN"]
)

registry.register(
    name="smartthings_set_mode",
    toolset="smartthings",
    schema={
        "name": "smartthings_set_mode",
        "description": "Change the current mode for a location (e.g. Home -> Away).",
        "parameters": {
            "type": "object",
            "properties": {
                "location_id": {"type": "string", "description": "Location UUID"},
                "mode_id": {"type": "string", "description": "Mode UUID"}
            },
            "required": ["location_id", "mode_id"]
        }
    },
    handler=lambda args, **kw: smartthings_set_mode(location_id=args.get("location_id"), mode_id=args.get("mode_id"), task_id=kw.get("task_id")),
    check_fn=_check_requirements,
    requires_env=["SMARTTHINGS_TOKEN"]
)

"""SmartThings location configuration manager.

Stores default location and known locations in ~/.hermes/smartthings_config.json.
All device/scene operations are scoped to a location — never mixed.
"""
import json
from pathlib import Path

from ._log import get_logger

logger = get_logger(__name__)

CONFIG_FILE = Path.home() / ".hermes" / "smartthings_config.json"


def _load() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text())
    except json.JSONDecodeError as e:
        logger.error("Config file corrupted: %s", e)
        return {}


def _save(data: dict):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2))


def get_default_location() -> str | None:
    """Return the configured default location ID, or None."""
    return _load().get("default_location_id")


def set_default_location(location_id: str):
    """Set the default location ID and persist to config."""
    cfg = _load()
    cfg["default_location_id"] = location_id
    _save(cfg)
    logger.info("Default location set to %s", location_id)


def get_locations() -> dict[str, dict]:
    """Return known locations map: {location_id: {"name": ...}}."""
    return _load().get("locations", {})


def add_location(location_id: str, name: str = ""):
    """Register a known location in config."""
    cfg = _load()
    if "locations" not in cfg:
        cfg["locations"] = {}
    cfg["locations"][location_id] = {"name": name}
    _save(cfg)
    logger.info("Added location %s (%s)", location_id, name or "unnamed")


def remove_location(location_id: str):
    """Remove a known location from config."""
    cfg = _load()
    if location_id not in cfg.get("locations", {}):
        return
    del cfg["locations"][location_id]
    if cfg.get("default_location_id") == location_id:
        cfg.pop("default_location_id", None)
    _save(cfg)
    logger.info("Removed location %s", location_id)


def resolve_location_id(location_id: str | None) -> str | None:
    """Return explicit location_id if given, else the configured default."""
    return location_id or get_default_location()

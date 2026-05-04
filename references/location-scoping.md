# Location Scoping Design

**Rule: devices, rooms, modes, and scenes are never mixed across locations.**

## Problem

A SmartThings account can have multiple locations (e.g., primary home + vacation home). Listing "all devices" across all locations produces a confusing mix. Device IDs are globally unique but operations should stay in context.

## Solution

### Config file
`~/.hermes/smartthings_config.json`:
```json
{
  "default_location_id": "abc123...",
  "locations": {
    "abc123...": {"name": "Home"},
    "def456...": {"name": "Lake House"}
  }
}
```

### `@_require_location` decorator

Wrapped on any tool that needs a location context:
```python
def _require_location(fn):
    @wraps(fn)
    def wrapper(c, location_id: str | None = None, *args, **kwargs):
        resolved = loc_config.resolve_location_id(location_id)
        if not resolved:
            return {
                "error": True,
                "message": (
                    "No location specified and no default location configured.\n"
                    "Run: smartthings_set_default_location(location_id='...')"
                ),
            }
        return fn(c, resolved, *args, **kwargs)
    return wrapper
```

Tools decorated with `@_require_location`:
- `smartthings_list_devices`
- `smartthings_list_rooms`
- `smartthings_list_modes`
- `smartthings_get_current_mode`
- `smartthings_set_mode`
- `smartthings_list_scenes`

### Behavior

| Call | Result |
|---|---|
| `smartthings_list_devices()` | Uses default location from config |
| `smartthings_list_devices(location_id="...")` | Uses explicit location |
| Both omitted and no config | Error: "No location specified and no default..." |

This is applied at the tool layer, not the core client layer, so the core client remains agnostic about location policy.

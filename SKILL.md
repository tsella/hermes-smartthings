---
name: smartthings
version: 0.1.0
author: Tom Sella
description: "Samsung SmartThings integration for Hermes Agent."
metadata:
  hermes:
    tags: [smarthome, samsung, smartthings, home-automation]
    requires: ["SMARTTHINGS_TOKEN"]
    platform: [cli, telegram, discord, whatsapp]
---

# Hermes SmartThings Integration

Direct SmartThings API control for Hermes Agent. No Home Assistant bridge required.

## Prerequisites

1. A Samsung SmartThings account
2. **Personal Access Token (PAT)** from [developer.smartthings.com](https://developer.smartthings.com/docs/getting-started/authorization-and-permissions)
3. Hermes Agent installed

## Setup

### Step 1 — Add token to `.env`

```bash
hermes config env-path  # Opens ~/.hermes/.env
```

Add:
```bash
SMARTTHINGS_TOKEN=pat-xxxx-xxxx-xxxx
```

### Step 2 — Install tool

Symlink the tool module into `hermes-agent/tools/` so it auto-registers:

```bash
ln -s "$PROJECT_ROOT/tools/smartthings_tool.py" "$HOME/.hermes/hermes-agent/tools/smartthings_tool.py"
```

Ensure `smartthings_core.py` and `requirements.txt` deps are resolvable. Best approach: clone to a known path and add it to PYTHONPATH, or keep `smartthings_core.py` next to the tool file:

```bash
# Option A: add project root to PYTHONPATH in shell profile
export HERMES_SMARTTHINGS_ROOT=/path/to/hermes-smartthings
```

The tool file uses this env var as a fallback import path.

### Step 3 — Enable toolset

```bash
hermes tools enable smartthings
```

Restart for discovery (`/reset` or new session).

### Step 4 — Verify

Ask Hermes:
> "List my SmartThings locations."

Expected response: JSON with `items` array containing location names and IDs.

---

## Tools

| Tool | Purpose | Typical Args |
|---|---|---|
| `smartthings_list_locations` | List all locations | None |
| `smartthings_list_devices` | List devices (optionally per location) | `location_id` (optional) |
| `smartthings_get_device` | Full device status + capabilities | `device_id` |
| `smartthings_send_command` | Execute a device command | `device_id`, `command` (e.g. "on","off"), optional `capability`, `arguments` |
| `smartthings_list_rooms` | Rooms within a location | `location_id` |
| `smartthings_list_modes` | Location modes | `location_id` |
| `smartthings_get_current_mode` | Current active mode | `location_id` |
| `smartthings_set_mode` | Change location mode | `location_id`, `mode_id` |

---

## Usage Examples

Tell Hermes:

> "Turn on the living room light."

Internal flow:
1. `smartthings_list_devices` → find "Living Room Light"
2. `smartthings_get_device` → inspect capabilities (confirm `switch` capability → `on` command)
3. `smartthings_send_command` → `{device_id: "xxx", command: "on"}`

---

> "Dim bedroom light to 40%."

Internal flow:
1. Find bedroom light device
2. `smartthings_get_device` → confirm `switchLevel` capability
3. `smartthings_send_command` → `{device_id: "xxx", command: "setLevel", arguments: {"level": 40}}`

---

> "Set the house to Away mode."

Internal flow:
1. `smartthings_list_locations` → get location ID
2. `smartthings_list_modes` → find "Away" mode ID
3. `smartthings_set_mode` → apply

---

## Safety & Warnings

- **No approval interlocks** — device commands execute immediately.
- Sensitive devices (locks, garage doors, HVAC) should trigger extra caution.
- Consider `hermes config set approvals.mode smart` for high-risk commands.
- The `_infer_capability` helper is heuristic. If a command fails, use `smartthings_get_device` to get exact `capability` IDs and pass them explicitly.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "SmartThings client unavailable" | `SMARTTHINGS_TOKEN` missing from `.env` or `smartthings_core.py` not on `PYTHONPATH` |
| HTTP 401 | Token expired or missing scopes. Regenerate PAT. |
| HTTP 403 | PAT lacks permission for that location/device. |
| Capability not found | Pass `capability` explicitly. Check `smartthings_get_device` output. |
| Device not responding | Verify device is online in SmartThings mobile app. |

## OAuth Alternative

SmartThings is deprecating long-lived PATs. For future-proofing, the repo keeps `client_id` and `client_secret` slots for OAuth 2.0 flow (not yet implemented). Track progress at: [github.com/tsella/hermes-smartthings/issues](https://github.com/tsella/hermes-smartthings/issues).

## References

- [SmartThings Capabilities Reference](https://developer.smartthings.com/docs/devices/capabilities/capabilities-reference)
- [SmartThings Public API Docs](https://developer.smartthings.com/docs/api/public)

## License
MIT

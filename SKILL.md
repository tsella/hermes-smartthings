---
name: smartthings
version: 0.2.0
author: Tom Sella
description: "Samsung SmartThings integration for Hermes Agent — PAT or OAuth."
metadata:
  hermes:
    tags: [smarthome, samsung, smartthings, home-automation]
    requires: ["SMARTTHINGS_TOKEN"]
    platform: [cli, telegram, discord, whatsapp]
---

# Hermes SmartThings Integration

Direct SmartThings API control for Hermes Agent. No Home Assistant bridge.

## Prerequisites

1. Samsung SmartThings account
2. One of:
   - **PAT** (Personal Access Token) — quick, but may expire in 24h for newly created tokens
   - **OAuth credentials** — client_id + client_secret from a registered SmartThings OAuth app. Persistent, auto-refreshing.

## Auth Setup

### Option A: PAT (fastest, for testing)

1. Visit [SmartThings Account → Personal Access Tokens](https://account.smartthings.com)
2. Generate a token with scopes: `r:devices:* w:devices:* r:locations:* r:rules:*`
3. Add to `~/.hermes/.env`:

```bash
SMARTTHINGS_TOKEN=pat-xxxx-xxxx-xxxx
```

### Option B: OAuth (recommended for daily use)

SmartThings PAT lifetime is shrinking. OAuth gives persistent access via refresh tokens.

1. **Register an OAuth app**:
   - Install [SmartThings CLI](https://developer.smartthings.com/docs/sdks/cli)
   - Run `smartthings apps:create` → choose **OAuth-In SmartApp**
   - Set a Display Name, Description, Permissions (`r:devices:* w:devices:* r:locations:* w:locations:*`)
   - Add Redirect URI: `http://127.0.0.1:8127/callback`
   - Save the generated **Client ID** and **Client Secret**

2. **Add credentials to `~/.hermes/.env`**:

```bash
SMARTTHINGS_CLIENT_ID=your_client_id
SMARTTHINGS_CLIENT_SECRET=your_client_secret
```

3. **Run the OAuth flow** (one-time setup):

```bash
cd ~/projects/hermes-smartthings
python -c "from auth import start_oauth_flow; start_oauth_flow('YOUR_CLIENT_ID', 'YOUR_CLIENT_SECRET')"
```

This opens a browser, asks you to log into SmartThings and authorize. Tokens are saved to `~/.hermes/smartthings_auth.json` and auto-refreshed before expiry.

## Hermes Integration

### 1. Install tool symlink

```bash
ln -s ~/projects/hermes-smartthings/tools/smartthings_tool.py ~/.hermes/hermes-agent/tools/smartthings_tool.py
```

### 2. Ensure PYTHONPATH

```bash
export HERMES_SMARTTHINGS_ROOT=~/projects/hermes-smartthings
# add to ~/.bashrc or ~/.zshrc for persistence
```

### 3. Enable toolset

```bash
hermes tools enable smartthings
```

Restart Hermes (`/reset` or new session).

### 4. Verify

> "List my SmartThings locations."

Expected: JSON with `items` array of locations.

---

## Tools

| Tool | Purpose | Typical Args |
|---|---|---|
| `smartthings_list_locations` | All locations | None |
| `smartthings_list_devices` | Devices (optionally per location) | `location_id` |
| `smartthings_get_device` | Full device profile + capabilities | `device_id` |
| `smartthings_get_device_status` | Real-time attribute values | `device_id` |
| `smartthings_send_command` | Execute a device command | `device_id`, `command` (e.g. "on", "off", "setLevel") |
| `smartthings_list_rooms` | Rooms in a location | `location_id` |
| `smartthings_list_modes` | Location modes | `location_id` |
| `smartthings_get_current_mode` | Active mode | `location_id` |
| `smartthings_set_mode` | Change location mode | `location_id`, `mode_id` |

---

## Usage Examples

> "Turn on the living room light."

Flow:
1. `smartthings_list_devices` → find "Living Room Light" ID
2. `smartthings_get_device` → verify `switch` capability, `on` command
3. `smartthings_send_command` → `{device_id: "xxx", command: "on"}`

---

> "Dim the bedroom light to 30%."

Flow:
1. Find bedroom light device
2. `smartthings_get_device_status` → confirm it's on, get current level
3. `smartthings_send_command` → `{device_id: "xxx", command: "setLevel", arguments: [30]}`

---

> "Set the house to Away mode."

Flow:
1. `smartthings_list_locations` → get location ID
2. `smartthings_list_modes` → find "Away" mode ID
3. `smartthings_set_mode` → apply

---

## Capability Quick Reference

| Command | Capability | Arguments |
|---|---|---|
| `on`, `off` | `switch` | none |
| `setLevel` | `switchLevel` | `[0-100]` |
| `setColor` | `colorControl` | `[{"hue":0-360,"saturation":0-100}]` |
| `lock`, `unlock` | `lock` | none |
| `setHeatingSetpoint` | `thermostatHeatingSetpoint` | `[temperature]` |
| `setCoolingSetpoint` | `thermostatCoolingSetpoint` | `[temperature]` |
| `setThermostatMode` | `thermostatMode` | `["heat","cool","auto","off"]` |
| `open`, `close` | `doorControl` | none |

If a command fails with "unknown command", pass `capability` explicitly and inspect the device with `smartthings_get_device`.

## Safety

- No approval interlocks by default. Sensitive devices (locks, garage doors) execute immediately.
- Consider `hermes config set approvals.mode smart` for prompting on high-risk commands.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "SmartThings client unavailable" | Set auth (PAT or OAuth) in `.env` / run OAuth flow |
| HTTP 401 | Token expired. PAT: regenerate. OAuth: delete `~/.hermes/smartthings_auth.json` and re-run flow. |
| HTTP 403 | Token lacks scope. Re-create with broader scopes. |
| "unknown command" | Pass `capability` explicitly. Use `smartthings_get_device` to inspect capabilities. |
| Device not responding | Check device online in SmartThings mobile app. |
| OAuth browser doesn't open | Manually visit the printed auth URL. |
| OAuth redirect URI mismatch | Ensure `http://127.0.0.1:8127/callback` is registered in your SmartThings OAuth app. |

## References

- [SmartThings Capabilities Reference](https://developer.smartthings.com/docs/devices/capabilities/capabilities-reference)
- [SmartThings Public API Docs](https://developer.smartthings.com/docs/api/public)
- [SmartThings OAuth Guide](https://developer.smartthings.com/docs/connected-services/oauth-integrations)

## License
MIT

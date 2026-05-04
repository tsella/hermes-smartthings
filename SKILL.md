---
name: smartthings
version: 0.5.1
author: Tom Sella
description: "Samsung SmartThings integration for Hermes Agent — domain-specific skill referencing the rest-api-tool-builder pattern."
license: MIT
metadata:
  hermes:
    tags: [smarthome, samsung, smartthings]
    related_skills: [rest-api-tool-builder, smart-home-rest-toolset]
    requires: []
---

# Hermes SmartThings Integration

Hermes toolset for Samsung SmartThings. Built using the **rest-api-tool-builder** pattern.

All device/scene/room/mode operations are **location-scoped** — never mixed across locations. Set a default location once and every tool that depends on location uses it automatically.

## Setup

### 1. Auth (pick one — checked in this order)

**A. PAT** (fastest, may expire in 24h):
```bash
# ~/.hermes/.env
SMARTTHINGS_TOKEN=pat-xxxx
```

**B. OAuth via SmartThings CLI** (zero-config — recommended if you already use the CLI):
```bash
npm install -g @smartthings/cli
smartthings login   # completes OAuth in browser
```
Hermes automatically reads tokens from `~/.config/@smartthings/cli/credentials.json`. No env vars needed.

**C. Custom OAuth app** (long-term, auto-refresh):
```bash
SMARTTHINGS_CLIENT_ID=xxx
SMARTTHINGS_CLIENT_SECRET=xxx
python -c "from hermes_smartthings.auth import start_oauth_flow; start_oauth_flow('YOUR_ID', 'YOUR_SECRET')"
```

---

### 2. SmartThings CLI OAuth on Headless Linux

The CLI tries to open a GUI browser automatically. On headless hosts, three approaches:

**Approach A — Use the CLI credentials bridge (easiest)**
Run `smartthings login` from a machine with a browser, then copy `~/.config/@smartthings/cli/credentials.json` to the headless host. Hermes will read it automatically.

⚠️ **The CLI credentials bridge (Approach A) is the preferred authentication method. Avoid modifying the SmartThings CLI JS.**

---

### 3. OAuth Bridge from CLI

This is implemented in `auth.py` via the `_load_cli_credentials()` fallback:
- `CLI_CREDENTIALS_FILE` = `~/.config/@smartthings/cli/credentials.json`
- Parses `accessToken`, `refreshToken`, `expires` from the `default` profile
- Refresh uses PKCE public-client grant (no `client_secret`)

See `references/hermes-integration.md` for the exact code pattern.

To enable the bridge, ensure `auth.py` contains:
- `CLI_CREDENTIALS_FILE` pointing to `~/.config/@smartthings/cli/credentials.json`
- `_load_cli_credentials()` to parse the JSON + extract `accessToken`, `refreshToken`, `expires`
- `_do_refresh_public()` for token refresh without `client_secret`
- Fallback in `get_token()` before returning None

See `references/hermes-integration.md` for the exact patch.

### 4. Hermes Toolset Registration

**Primary way (zero core patches):**

Drop a tool file in `~/.hermes/hermes-agent/tools/` that calls `registry.register()`, and Hermes auto-discovers it. The `check_fn` controls whether the toolset appears in the schema based on runtime auth state.

For this project, symlink the tool file and install the package:
```bash
ln -s ~/projects/hermes-smartthings/tools/smartthings_tool.py ~/.hermes/hermes-agent/tools/
pip install -e ~/projects/hermes-smartthings
```

That's it. The AI can use the tools immediately. No core Hermes code needs to change.

**Pitfall (learned the hard way):** Do NOT patch core Hermes (`toolsets.py`, `tools_config.py`, `config.yaml`) to get the toolset visible in `hermes tools list`. Those patches are purely cosmetic (TUI checklist) and break on every Hermes update. If you need the toolset in the TUI checklist, accept that core patches are temporary and document them separately. The tools themselves work via auto-discovery alone.

See `references/modular-tool-discovery.md` for why this works and how to verify it.

See `references/hermes-integration.md` for the full (optional) core patch instructions, but prefer the zero-core-patch approach above.

## Available Tools

| Tool | Purpose |
|---|---|
| `smartthings_set_default_location` | Set the default location for scoping |
| `smartthings_get_default_location` | Read the configured default location |
| `smartthings_list_locations` | List all locations |
| `smartthings_list_devices` | Devices **scoped to configured location** |
| `smartthings_get_device` | Full profile + capabilities |
| `smartthings_get_device_status` | Real-time attribute values |
| `smartthings_send_command` | Execute commands (on, off, setLevel, lock, etc.) |
| `smartthings_list_rooms` | Rooms in the default location |
| `smartthings_list_modes` | Location modes (default location) |
| `smartthings_get_current_mode` | Active mode (default location) |
| `smartthings_set_mode` | Change mode (default location) |
| `smartthings_list_scenes` | Scenes in the default location |
| `smartthings_execute_scene` | Run a scene by ID |

## Location Scoping

**Devices, rooms, modes, and scenes are NEVER mixed across locations.**
All tools that accept `location_id` use a `@_require_location` decorator that:
1. Returns the explicit `location_id` if provided
2. Falls back to the configured default from `~/.hermes/smartthings_config.json`
3. Returns a clear error if neither is set

### How to handle "no default location"

If a location-scoped call fails because no default is configured, the AI **must**:
1. Call `smartthings_list_locations`
2. Show the list to the user
3. Ask which location to use
4. Call `smartthings_set_default_location(location_id="...")` with the user's choice
5. Retry the original operation

This only needs to happen once — after `set_default_location`, all subsequent calls are automatically scoped.

## Common Commands

| Command | Capability | Args |
|---|---|---|
| `on`, `off` | `switch` | none |
| `setLevel` | `switchLevel` | `[0-100]` |
| `setColor` | `colorControl` | `[{"hue":0-360,"saturation":0-100}]` |
| `lock`, `unlock` | `lock` | none |
| `open` | `doorControl` | none |
| `close` | `windowShade` | none |
| `pause` | `mediaPlayback` | none |
| `play`, `stop` | `mediaPlayback` | none |
| `setVolume`, `volumeUp`, `volumeDown` | `audioVolume` | `[0-100]` or none |

## Capability Auto-Inference

`send_command` automatically maps common commands to capabilities:
- `on`/`off` → `switch`
- `setLevel` → `switchLevel`
- `lock`/`unlock` → `lock`
- `open` → `doorControl`
- `close` → `windowShade` (shades and blinds)
- `play`/`pause`/`stop` → `mediaPlayback`
- `setVolume`/`volumeUp`/`volumeDown` → `audioVolume`

Pass `capability` explicitly if a command fails or isn't in the known map.

## Logging

All operations are logged to `~/.hermes/logs/smartthings.log`:
- 50 MB rotation, 7-day retention
- Timestamps, levels, file:function:line in every line
- **All tokens, passwords, and secrets are automatically redacted**

**Log level is configurable** via `~/.hermes/smartthings_config.json`:

```json
{
  "log_level": "DEBUG",
  "console_log_level": "WARNING"
}
```

Valid values: `DEBUG`, `INFO` (default), `WARNING`, `ERROR`, `CRITICAL`. The `console_log_level` controls stderr output independently (defaults to `WARNING`).

## Samsung TV Pitfalls

### Don't trust the `label` / `name` field for device identification

Samsung TVs often have **stale or incorrect `label`/`name` values** in SmartThings (e.g., `"Samsung The Frame 65"` when the actual hardware is an OLED TV). The `label` field is user-editable and may retain old names from previous setups, Art Mode configurations, or factory defaults.

**Use the OCF `mnmo` (model number) field instead:**
```python
ocf = status["components"]["main"]["ocf"]
model = ocf["mnmo"]["value"]   # e.g., "QE65LS03BGUXSQ"
```

### HTTP 409 "invalid device state" on `switch:off`

Some Samsung TVs reject the standard `switch:off` command with HTTP 409. **Do not assume this is a Frame TV Art Mode issue** — it can happen on any Samsung TV where the firmware/OCF state machine is in a transitional or locked state.

**When 409 occurs:**
1. Re-read device status to confirm `switch` still reports `"on"`
2. Try `samsungvd.remoteControl:send` with key `"EXIT"` or `"HOME"` first (kick the TV out of any modal state)
3. Retry `switch:off`
4. If still 409, the TV's OCF firmware is likely rejecting the command; fall back to asking the user to use the physical remote or Samsung mobile app

**`samsungvd.remoteControl` valid keys:** UP, DOWN, LEFT, RIGHT, OK, BACK, EXIT, MENU, HOME, MUTE, PLAY, PAUSE, STOP, REWIND, FF, PLAY_BACK, SOURCE. **No POWER key.**

### "App" field hallucinations

The `tvChannelName` attribute (e.g., `"org.tizen.netflix-app"`) is **often stale cached data** from the last active app, not the current app. The null `playbackStatus`, empty `tvChannel`, and explicit `"Idle"` `thingStatus` are the reliable signals. Do not report an app as active when these contradict it.

## Safety

- Commands execute immediately (no approval interlocks by default)
- Set `approvals.mode: smart` for high-risk devices (locks, garage doors)

## Troubleshooting

| Symptom | Fix |
|---|---|
| "client unavailable" | Check auth (PAT env or OAuth file) |
| HTTP 401 | Token expired. Regenerate PAT or re-run OAuth flow |
| "unknown command" | Pass explicit `capability` |
| "No default location configured" | Call `smartthings_list_locations`, ask user to pick, then `smartthings_set_default_location` |
| CLI tries to open browser on headless host | Run `smartthings login` on a machine with a browser, then copy `~/.config/@smartthings/cli/credentials.json` to the headless host. Hermes reads it automatically. |

## API Response Shapes

**Pitfall:** SmartThings REST endpoints return wrapped dicts, not bare lists.
- `list_devices` → `{"items": [...]}`
- `get_device_status` → `{"components": {"main": {...}}}`
- `list_scenes` → `{"items": [...]}`
- `list_locations` → `{"items": [...]}`
- `get_current_mode` → single dict (not wrapped)

See `references/api-response-shapes.md` for full examples and safe access patterns.

- `references/shade-commands.md` — windowShade commands, status interpretation, `close` vs `doorControl` pitfall
## References

- [SmartThings Capabilities](https://developer.smartthings.com/docs/devices/capabilities/capabilities-reference)
- [SmartThings OAuth Guide](https://developer.smartthings.com/docs/connected-services/oauth-integrations)
- `references/api-response-shapes.md` — common API response structures and safe parsing patterns
- `references/location-scoping.md` — design notes on the `@_require_location` pattern and config file format
- `references/samsung-tv-http-409.md` — debugging Samsung TV power-off failures (HTTP 409 invalid device state)

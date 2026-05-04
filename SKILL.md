---
name: smartthings
version: 2.0.0
author: Tom Sella
description: "Samsung SmartThings integration for Hermes Agent — unified tool with scene preflight and semantic command dispatch."
license: MIT
metadata:
  hermes:
    tags: [smarthome, samsung, smartthings]
    related_skills: [rest-api-tool-builder, smart-home-rest-toolset]
    requires: []
---

# Hermes SmartThings Integration

One tool. Scene-aware. Semantic dispatch. No UUIDs.

```python
smartthings(action, target="", value="", location_id="")
```

| Action | Target | Value | Example |
|---|---|---|---|
| `list` | `devices` / `scenes` / `modes` / `rooms` / `locations` | — | `smartthings("list", "devices")` |
| `get` | device name or ID | — | `smartthings("get", "Shade #1")` |
| `set` | device(s) name, group, or ID | command | `smartthings("set", "shades", "open")` |
| `scene` | scene name or ID | — | `smartthings("scene", "Movie Night")` |
| `mode` | mode name or ID | — | `smartthings("mode", "Away")` |
| `location` | location name | — | `smartthings("location", "35E38St")` |

## Scene Preflight

Before sending individual device commands, the tool checks if a **named scene matches the user's intent** and executes it instead.

```python
smartthings("set", "shades", "open")
# → Executes "Window Shade: Open" scene if it exists
# → Falls back to individual device commands if no matching scene
```

This works for any scene named with a pattern like `[Thing]: [Action]` — e.g. `Window Shade: Open`, `Movie Night`, etc.

## Semantic Command Dispatch

The same word means different commands depending on the device type:

| User says | Shades | TVs / Projectors | Locks | Speakers |
|---|---|---|---|---|
| `open` | `windowShade.open` | `switch.on` | — | — |
| `close` | `windowShade.close` | `switch.off` | `lock.lock` | — |
| `on` | `switch.on` | `switch.on` | — | `switch.on` |
| `off` | `switch.off` | `switch.off` | — | `switch.off` |
| `pause` | — | `mediaPlayback.pause` | — | `mediaPlayback.pause` |
| `lock` | — | — | `lock.lock` | — |
| `unlock` | — | — | `lock.unlock` | — |

```python
smartthings("set", "Frame 43", "on")       # → switch.on
smartthings("set", "Shade #1", "open")     # → windowShade.open
smartthings("set", "projector", "close")   # → switch.off
```

## Group / Plural Targets

Target can be a group keyword. The tool resolves all matching devices:

| Target | Matches devices with... |
|---|---|
| `shades`, `blinds` | `windowShade` capability |
| `tvs`, `televisions` | Category = Television |
| `projectors` | Category = Projector |
| `lights`, `switches` | `switch` capability |
| `speakers` | `audioVolume` capability |
| `doors`, `locks` | `lock` capability |
| `all shades`, `all tvs` | Same as above |

```python
smartthings("set", "all tvs", "off")       # → switch.off on Frame 43 + 55" OLED
smartthings("set", "shades", "close")      # → scene preflight first, then device dispatch
```

## Setup

### 1. Auth (pick one)

**A. PAT** (fastest, may expire in 24h):
```bash
# ~/.hermes/.env
SMARTTHINGS_TOKEN=pat-xxxx
```

**B. OAuth via SmartThings CLI** (recommended):
```bash
npm install -g @smartthings/cli
smartthings login   # on a machine with a browser
```
Then copy `~/.config/@smartthings/cli/credentials.json` to the Hermes host.

**C. Custom OAuth app** (long-term, auto-refresh):
```bash
SMARTTHINGS_CLIENT_ID=xxx
SMARTTHINGS_CLIENT_SECRET=xxx
python -c "from hermes_smartthings.auth import start_oauth_flow; start_oauth_flow('YOUR_ID', 'YOUR_SECRET')"
```

### 2. Install into Hermes venv

```bash
ln -s ~/projects/hermes-smartthings/tools/smartthings_tool.py ~/.hermes/hermes-agent/tools/

HERMES_PY="$(ls ~/.hermes/hermes-agent/.venv/bin/python ~/.hermes/hermes-agent/venv/bin/python 2>/dev/null | head -1)"
uv pip install -e ~/projects/hermes-smartthings --python "$HERMES_PY"

# Verify
"$HERMES_PY" -c "import hermes_smartthings; print('ok')"
```

**Pitfall:** Do NOT patch core Hermes (`toolsets.py`, `tools_config.py`, `config.yaml`) for TUI visibility. Those patches break on every update. Auto-discovery works immediately.

## Location Scoping

```python
smartthings("location", "35E38St")   # one-time setup
smartthings("list", "devices")       # auto-scoped
```

## Logging

All operations log to `~/.hermes/logs/smartthings.log`:
- 50 MB rotation, 7-day retention
- Timestamps, levels, file:function:line
- **Tokens and secrets automatically redacted**

Config via `~/.hermes/smartthings_config.json`:
```json
{"log_level": "DEBUG", "console_log_level": "WARNING"}
```

## Samsung TV Pitfalls

### HTTP 409 "invalid device state"

Samsung TVs sometimes reject `switch:on`/`off` with HTTP 409 when the OCF state machine is transitional.

1. Confirm `switch` still reports `"on"` via `get`
2. Try `samsungvd.remoteControl:send` with key `"EXIT"` or `"HOME"`
3. Retry `switch:off`
4. If still 409, use physical remote

**Valid remoteControl keys:** UP, DOWN, LEFT, RIGHT, OK, BACK, EXIT, MENU, HOME, MUTE, PLAY, PAUSE, STOP, REWIND, FF, SOURCE. **No POWER key.**

### Don't trust `tvChannelName`

Often stale cached data. Trust `thingStatus: Idle` + null `playbackStatus` over app names.

## Safety

- Commands execute immediately (no approval interlocks by default)
- Set `approvals.mode: smart` for high-risk devices (locks, garage doors)

## References

- `references/samsung-tv-http-409.md` — Samsung TV power-off debugging

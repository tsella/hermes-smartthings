---
name: smartthings
version: 1.0.0
author: Tom Sella
description: "Samsung SmartThings integration for Hermes Agent — unified single-tool interface."
license: MIT
metadata:
  hermes:
    tags: [smarthome, samsung, smartthings]
    related_skills: [rest-api-tool-builder, smart-home-rest-toolset]
    requires: []
---

# Hermes SmartThings Integration

One tool. Six actions. No UUIDs required.

```python
smartthings(action, target="", value="", location_id="")
```

| Action | Target | Value | Example |
|---|---|---|---|
| `list` | `devices` / `scenes` / `modes` / `rooms` / `locations` | — | `smartthings("list", "devices")` |
| `get` | device name or ID | — | `smartthings("get", "Shade #1")` |
| `set` | device name or ID | command | `smartthings("set", "Shade #1", "close")` |
| `scene` | scene name or ID | — | `smartthings("scene", "Movie Night")` |
| `mode` | mode name or ID | — | `smartthings("mode", "Away")` |
| `location` | location name | — | `smartthings("location", "35E38St")` |

Name matching is fuzzy — `"Frame 43"`, `"OLED"`, `"Shade"` all resolve automatically. Only one tool registers with Hermes: **`smartthings`**.

---

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
Then copy `~/.config/@smartthings/cli/credentials.json` to the Hermes host. Hermes reads it automatically. No env vars needed.

**C. Custom OAuth app** (long-term, auto-refresh):
```bash
SMARTTHINGS_CLIENT_ID=xxx
SMARTTHINGS_CLIENT_SECRET=xxx
python -c "from hermes_smartthings.auth import start_oauth_flow; start_oauth_flow('YOUR_ID', 'YOUR_SECRET')"
```

### 2. Install into Hermes venv

```bash
# Symlink the tool file so Hermes auto-discovers it
ln -s ~/projects/hermes-smartthings/tools/smartthings_tool.py ~/.hermes/hermes-agent/tools/

# Install the package into the same interpreter Hermes uses
HERMES_PY="$(ls ~/.hermes/hermes-agent/.venv/bin/python ~/.hermes/hermes-agent/venv/bin/python 2>/dev/null | head -1)"
uv pip install -e ~/projects/hermes-smartthings --python "$HERMES_PY"

# Verify
"$HERMES_PY" -c "import hermes_smartthings; print('ok')"
```

**Pitfall:** If `import hermes_smartthings` fails from the Hermes interpreter, the tools won't work — the symlink alone is not enough.

**Pitfall:** Do NOT patch core Hermes (`toolsets.py`, `tools_config.py`, `config.yaml`) to get TUI visibility. Those patches break on every update. The zero-core-patch auto-discovery approach works immediately.

---

## Location Scoping

Devices, scenes, modes, and rooms are **never mixed across locations**. After setting a default location once, all subsequent calls are auto-scoped:

```python
smartthings("location", "35E38St")   # one-time setup
smartthings("list", "devices")       # uses default automatically
smartthings("set", "Shade #1", "close")
```

If no default is set, `list`/`get`/`set` scope calls return:
```json
{"error": "No default location. Run set location \u003cname\u003e first."}
```

The AI should then:
1. `smartthings("list", "locations")`
2. Ask the user which one
3. `smartthings("location", "\u003cname\u003e")`
4. Retry the original call

---

## Common Commands

| Value | Capability | Notes |
|---|---|---|
| `on`, `off` | `switch` | TVs, lights, outlets |
| `open`, `close` | `windowShade` | Shades and blinds |
| `pause` | `mediaPlayback` | Media players |
| `play`, `stop` | `mediaPlayback` | |
| `setVolume`, `volumeUp`, `volumeDown` | `audioVolume` | `[0-100]` or no args |
| `setLevel` | `switchLevel` | `[0-100]` |
| `lock`, `unlock` | `lock` | |
| `setColor` | `colorControl` | `[{"hue":0-360,"saturation":0-100}]` |

Commands are auto-mapped to capabilities. Pass explicit capability only if auto-inference fails.

---

## Logging

All operations log to `~/.hermes/logs/smartthings.log`:
- 50 MB rotation, 7-day retention
- Timestamps, levels, file:function:line
- **Tokens and secrets automatically redacted**

Config via `~/.hermes/smartthings_config.json`:
```json
{
  "log_level": "DEBUG",
  "console_log_level": "WARNING"
}
```

---

## Samsung TV Pitfalls

### Don't trust `label` / `name`

Samsung TVs often have stale labels. Use the OCF `mnmo` field:
```python
ocf = status["components"]["main"]["ocf"]
model = ocf["mnmo"]["value"]   # e.g., "QN43LS03BAFXZA"
```

### HTTP 409 "invalid device state" on `switch:off`

1. Re-read status to confirm `switch` still reports `"on"`
2. Try `samsungvd.remoteControl:send` with key `"EXIT"` or `"HOME"`
3. Retry `switch:off`
4. If still 409, OCF firmware is rejecting the command

**Valid remoteControl keys:** UP, DOWN, LEFT, RIGHT, OK, BACK, EXIT, MENU, HOME, MUTE, PLAY, PAUSE, STOP, REWIND, FF, SOURCE. **No POWER key.**

### "App" field hallucinations

`tvChannelName` is often stale cached data. Trust `thingStatus: Idle` + null `playbackStatus` over app names.

---

## Safety

- Commands execute immediately (no approval interlocks by default)
- Set `approvals.mode: smart` for high-risk devices (locks, garage doors)

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "client unavailable" | Check auth (PAT env or OAuth file) |
| HTTP 401 | Token expired. Regenerate PAT or re-run OAuth |
| "unknown command" | Pass explicit `capability` |
| "No default location" | Call `smartthings("location", "\u003cname\u003e")` |
| "ModuleNotFoundError" | Package not installed in Hermes venv |
| CLI tries to open browser | Run `smartthings login` on a machine with a browser, copy `credentials.json` |

## References

- `references/api-response-shapes.md` — safe parsing patterns for wrapped API responses
- `references/samsung-tv-http-409.md` — Samsung TV power-off debugging
- `references/modular-tool-discovery.md` — zero-core-patch auto-discovery verification

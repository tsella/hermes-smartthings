# Hermes SmartThings Integration

SmartThings API client + Hermes skill for controlling Samsung SmartThings devices, locations, rooms, modes, and scenes.

## Auth Setup

Three token sources are checked in this order:

1. **PAT** (quickest, may expire in 24h)
   ```bash
   # Add to ~/.hermes/.env
   SMARTTHINGS_TOKEN=pat-xxxx-xxxx-xxxx
   ```

2. **OAuth via SmartThings CLI** (zero-config fallback)
   ```bash
   npm install -g @smartthings/cli
   smartthings login
   ```
   Hermes automatically reads tokens from `~/.config/@smartthings/cli/credentials.json`.

3. **OAuth via custom app** (recommended for long-term use)
   1. `smartthings apps:create`
   2. Add to `~/.hermes/.env`:
      ```bash
      SMARTTHINGS_CLIENT_ID=your_id
      SMARTTHINGS_CLIENT_SECRET=your_secret
      ```
   3. Run flow:
      ```bash
      python -c "from hermes_smartthings.auth import start_oauth_flow; start_oauth_flow('YOUR_ID', 'YOUR_SECRET')"
      ```

## Install into Hermes

### 1. Install the Python package

```bash
cd ~/projects/hermes-smartthings
pip install -e .
# Or with --break-system-packages if needed on Ubuntu/Debian
```

### 2. Symlink the tool file

```bash
ln -s ~/projects/hermes-smartthings/tools/smartthings_tool.py \
      ~/.hermes/hermes-agent/tools/smartthings_tool.py
```

### 3. Copy the skill (optional but recommended)

```bash
mkdir -p ~/.hermes/skills/smartthings/references
ln -sf ~/projects/hermes-smartthings/SKILL.md ~/.hermes/skills/smartthings/SKILL.md
ln -sf ~/projects/hermes-smartthings/references/* ~/.hermes/skills/smartthings/references/
```

### 4. Start a new Hermes session

```
/reset
```

The tools auto-register at startup. No core Hermes patches are needed.

## Setting your default location

Device, room, mode, and scene operations are scoped to a single location. On first use:

1. The AI calls `smartthings_list_locations`
2. You pick a location from the list
3. The AI calls `smartthings_set_default_location(location_id="...")`
4. All subsequent operations use that location automatically

## Features

- List locations, rooms, devices, modes, scenes
- Get device profile + real-time status
- Send commands (on/off/setLevel/lock/setColor/open/close/etc.)
- Execute scenes
- Capability auto-inference for common commands
- PAT or OAuth with automatic refresh
- OAuth token bridge from SmartThings CLI
- **Comprehensive logging** with redaction (~/.hermes/logs/smartthings.log)

## Logging

All operations are logged to `~/.hermes/logs/smartthings.log`:
- 50 MB rotation, 7-day retention
- Timestamps, levels, file:function:line in every line
- **All tokens, passwords, and secrets are automatically redacted**
- DEBUG: API URLs, response statuses
- INFO: Actions taken (commands sent, modes changed, scenes executed)
- WARNING: API errors, missing tokens
- ERROR: Network failures, unrecoverable issues

**Log level is configurable** via `~/.hermes/smartthings_config.json`:

```json
{
  "log_level": "DEBUG"
}
```

Valid values: `DEBUG`, `INFO` (default), `WARNING`, `ERROR`, `CRITICAL`.

Console (stderr) output defaults to `WARNING`; override with `console_log_level`.

## Structure

```
~/projects/hermes-smartthings/
├── src/hermes_smartthings/
│   ├── __init__.py
│   ├── _log.py              # Rotating, redacting logger
│   ├── auth.py              # PAT + OAuth + CLI bridge
│   ├── config.py            # Location configuration store
│   └── smartthings_core.py  # API client
├── tools/
│   └── smartthings_tool.py  # Hermes tool registration
├── references/
│   ├── headless-oauth-patch.md
│   ├── hermes-integration.md
│   ├── location-scoping.md
│   └── modular-tool-discovery.md
├── SKILL.md                 # Hermes skill file
├── pyproject.toml
└── README.md
```

## License
MIT

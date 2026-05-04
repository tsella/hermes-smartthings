# Hermes SmartThings Integration

SmartThings API client + Hermes skill for controlling Samsung SmartThings devices, locations, rooms, and modes.

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
      cd ~/projects/hermes-smartthings
      python -c "from hermes_smartthings.auth import start_oauth_flow; start_oauth_flow('YOUR_ID', 'YOUR_SECRET')"
      ```

## Install into Hermes

```bash
ln -s ~/projects/hermes-smartthings/tools/smartthings_tool.py ~/.hermes/hermes-agent/tools/smartthings_tool.py
export HERMES_SMARTTHINGS_ROOT=~/projects/hermes-smartthings
hermes tools enable smartthings
# /reset or new session
```

## Features

- List locations, rooms, devices, modes
- Get device profile + real-time status
- Send commands (on/off/setLevel/lock/setColor/etc.)
- Capability auto-inference for common commands
- PAT or OAuth with automatic refresh
- **Comprehensive logging** with redaction (~/.hermes/logs/smartthings.log)

## Logging

All operations are logged to `~/.hermes/logs/smartthings.log`:
- 50 MB rotation, 7-day retention
- Timestamps, levels, file:function:line in every line
- **All tokens, passwords, and secrets are automatically redacted**
- DEBUG: API URLs, response statuses
- INFO: Actions taken (commands sent, modes changed)
- WARNING: API errors, missing tokens
- ERROR: Network failures, unrecoverable issues

## License
MIT

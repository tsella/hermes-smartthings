# Hermes SmartThings Integration

SmartThings API client + Hermes skill for controlling Samsung SmartThings devices, locations, rooms, and modes through Hermes Agent.

## Repository
https://github.com/tsella/hermes-smartthings

## Auth Setup

### Quick (PAT — may expire in 24h)
```bash
# Add to ~/.hermes/.env
SMARTTHINGS_TOKEN=pat-xxxx-xxxx-xxxx
```

### Recommended (OAuth — persistent, auto-refresh)
1. Register an OAuth-In SmartApp via [SmartThings CLI](https://developer.smartthings.com/docs/sdks/cli):
   ```bash
   smartthings apps:create
   # Choose OAuth-In SmartApp, set name, scopes, redirect URI: http://127.0.0.1:8127/callback
   ```
2. Add to `~/.hermes/.env`:
   ```bash
   SMARTTHINGS_CLIENT_ID=your_client_id
   SMARTTHINGS_CLIENT_SECRET=your_client_secret
   ```
3. Run OAuth flow:
   ```bash
   cd ~/projects/hermes-smartthings
   python -c "from auth import start_oauth_flow; start_oauth_flow('YOUR_CLIENT_ID', 'YOUR_CLIENT_SECRET')"
   ```
   Tokens saved to `~/.hermes/smartthings_auth.json`, auto-refreshed before expiry.

## Install into Hermes

```bash
# Symlink the tool file
ln -s ~/projects/hermes-smartthings/tools/smartthings_tool.py ~/.hermes/hermes-agent/tools/smartthings_tool.py

# Ensure PYTHONPATH includes project root
export HERMES_SMARTTHINGS_ROOT=~/projects/hermes-smartthings

# Enable toolset
hermes tools enable smartthings
# /reset or new session for discovery
```

## Test
```bash
export SMARTTHINGS_TOKEN=pat-xxxx
python test_client.py
```

## Features

- List locations, rooms, devices, modes
- Get device profile + real-time status
- Send device commands (on, off, setLevel, lock, setColor, etc.)
- Change location modes
- Capability auto-inference for common commands
- PAT or OAuth authentication with automatic refresh

## Project Structure

| File | Purpose |
|---|---|
| `smartthings_core.py` | Low-level REST client |
| `auth.py` | PAT + OAuth 2.0 auth manager |
| `tools/smartthings_tool.py` | Hermes tool registrations |
| `SKILL.md` | Usage guide & examples |
| `test_client.py` | Manual test script |

## License
MIT

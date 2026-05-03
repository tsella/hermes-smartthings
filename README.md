# Hermes SmartThings Integration

SmartThings API client + Hermes skill for controlling Samsung SmartThings devices, locations, rooms, and modes through Hermes Agent.

## Repository
https://github.com/tsella/hermes-smartthings

## Quick Start

### 1. Install
```bash
# Clone
git clone https://github.com/tsella/hermes-smartthings.git
cd hermes-smartthings

# Install Python deps
pip install -r requirements.txt
```

### 2. Authenticate
Get a **Personal Access Token (PAT)** from [SmartThings Developer Portal](https://developer.smartthings.com/docs/getting-started/authorization-and-permissions) (Account → Personal Access Tokens).

Add to Hermes `.env`:
```bash
SMARTTHINGS_TOKEN=pat-xxxx-xxxx-xxxx
SMARTTHINGS_CLIENT_ID=optional_oauth_client_id
SMARTTHINGS_CLIENT_SECRET=optional_oauth_client_secret
```

> **Warning:** Samsung is moving toward OAuth-based SmartApp flows. The 24-hour PAT TTL policy may affect new tokens. OAuth client credentials allow building a persistent integration if needed.

### 3. Integrate with Hermes
#### Option A: Symlink tool file (recommended)
```bash
ln -s "$(pwd)/tools/smartthings_tool.py" "$HOME/.hermes/hermes-agent/tools/smartthings_tool.py"
```
Restart Hermes for tool discovery (`/reset` or exit + relaunch).

#### Option B: Skill-based (no file copy)
Install the skill into Hermes:
```bash
hermes skills install "https://raw.githubusercontent.com/tsella/hermes-smartthings/main/SKILL.md" --name smartthings
```
Then invoke via `/skill smartthings` and use web tools + device IDs from exploration steps in the skill guide.

### 4. Test
```bash
# From project root
python -c "from smartthings_core import get_client; c=get_client(); print(c.list_locations())"
```

## Features

- List locations, rooms, devices, modes
- Get device status & capabilities
- Send device commands (on, off, setLevel, setColor, lock, unlock, etc.)
- Change location modes (Home, Away, etc.)
- Capability auto-inference or explicit specification

## Architecture

- `smartthings_core.py` — Low-level REST client (`SmartThingsClient`)
- `tools/smartthings_tool.py` — Hermes tool registrations
- `SKILL.md` — Usage guide, examples, safety notes
- `test_client.py` — Manual test script

## Device & Capability Examples

| Device Type | Capability | Common Commands |
|---|---|---|
| Light / Switch | switch | on, off |
| Dimmer | switchLevel | setLevel (0-100) |
| Color Bulb | colorControl | setColor (hue/saturation/value) |
| Thermostat | thermostat | setHeatingSetpoint, setCoolingSetpoint, setThermostatMode |
| Lock | lock | lock, unlock |
| Motion Sensor | motionSensor | (read-only: active/inactive) |
| Contact Sensor | contactSensor | (read-only: open/close) |

See [SmartThings Capabilities Reference](https://developer.smartthings.com/docs/devices/capabilities/capabilities-reference) for full details.

## Safety

This tool has **no approval interlocks** by default. It will execute device commands immediately. If your environment includes locks, garage doors, or HVAC, consider setting:
```bash
hermes config set approvals.mode smart
```
to auto-approve low-risk commands and prompt on high-risk ones.

## License
MIT

# Hermes Agent Integration — SmartThings Toolset

Complete walkthrough for wiring a custom SmartThings Python toolset into Hermes Agent.

## Context

Hermes discovers tools by importing `*.py` files under `~/.hermes/hermes-agent/tools/`. Each file calls `registry.register()` at module level. This is **sufficient** — the tools work without any core changes.

If you also want the toolset visible in `hermes tools list`, patch 3 additional core files. Core patches are cosmetic (TUI visibility) and break on update.

---

## Zero-patch approach (recommended)

1. Create your tool file (e.g. `tools/smartthings_tool.py`)
2. Call `registry.register()` for each tool at module level
3. Symlink into Hermes:
   ```bash
   ln -s ~/projects/hermes-smartthings/tools/smartthings_tool.py ~/.hermes/hermes-agent/tools/
   ```
4. Done. The AI can use the tools immediately.

---

## Cosmetic-only patches (if you want `hermes tools list` TUI)

These make the toolset appear in the checklist. Skip them unless you specifically need that.

---

## Step 1 — Tool file + symlink

Your tool file (`tools/smartthings_tool.py`) must:

- Import `tools.registry.registry` and call `registry.register()` for each tool
- Provide a `check_fn` that returns `False` (never raises) when auth is missing
- Resolve imports via `HERMES_SMARTTHINGS_ROOT` env var fallback or `sys.path`

Symlink into Hermes:
```bash
ln -s ~/projects/hermes-smartthings/tools/smartthings_tool.py \
      ~/.hermes/hermes-agent/tools/smartthings_tool.py
```

---

## Step 2 — Patch `toolsets.py`

File: `~/.hermes/hermes-agent/toolsets.py`

### A. Add tool names to `_HERMES_CORE_TOOLS`

Find the `_HERMES_CORE_TOOLS` list (around line 31). Add your tool names after the Home Assistant block:

```python
    # Home Assistant smart home control (gated on HASS_TOKEN via check_fn)
    "ha_list_entities", "ha_get_state", "ha_list_services", "ha_call_service",
    # SmartThings smart home control (gated on auth via check_fn)
    "smartthings_list_locations", "smartthings_list_devices", "smartthings_get_device",
    "smartthings_get_device_status", "smartthings_send_command", "smartthings_list_rooms",
    "smartthings_list_modes", "smartthings_get_current_mode", "smartthings_set_mode",
    "smartthings_set_default_location", "smartthings_get_default_location",
    "smartthings_list_scenes", "smartthings_execute_scene",
    # Kanban ...
```

**Why:** `_HERMES_CORE_TOOLS` is the master allowlist. Tools not in this list are invisible even if registered.

### B. Add toolset to `TOOLSETS`

Find the `TOOLSETS` dict (around line 73). Insert a new entry after `homeassistant`:

```python
    "smartthings": {
        "description": "Samsung SmartThings smart home control and monitoring",
        "tools": [
            "smartthings_list_locations", "smartthings_list_devices", "smartthings_get_device",
            "smartthings_get_device_status", "smartthings_send_command", "smartthings_list_rooms",
            "smartthings_list_modes", "smartthings_get_current_mode", "smartthings_set_mode",
            "smartthings_set_default_location", "smartthings_get_default_location",
            "smartthings_list_scenes", "smartthings_execute_scene"
        ],
        "includes": []
    },
```

**Why:** `TOOLSETS` maps a human-readable toolset name → list of tool names. Used by `resolve_toolset()` and `get_tool_names_for_toolset()`.

---

## Step 3 — Patch `hermes_cli/tools_config.py`

File: `~/.hermes/hermes-agent/hermes_cli/tools_config.py`

### A. Add to `CONFIGURABLE_TOOLSETS`

Find the `CONFIGURABLE_TOOLSETS` list (around line 52). Insert:

```python
    ("smartthings", "🏠 SmartThings", "Samsung SmartThings device control"),
```

**Why:** This list drives the `hermes tools` TUI. Without it, the toolset is invisible to users.

### B. Add to `_DEFAULT_OFF_TOOLSETS`

Find `_DEFAULT_OFF_TOOLSETS` (around line 81). Insert `smartthings`:

```python
_DEFAULT_OFF_TOOLSETS = {"moa", "homeassistant", "smartthings", "rl", "spotify", "discord", "discord_admin"}
```

**Why:** Default-off means new users don't get SmartThings tools cluttering their schema unless they explicitly enable it via `hermes tools`.

---

## Step 4 — Patch `~/.hermes/config.yaml`

Under `platform_toolsets:`, add `smartthings` to the `cli` list:

```yaml
platform_toolsets:
  cli:
  - browser
  - clarify
  - code_execution
  - ...
  - smartthings
```

**Why:** `_get_platform_tools()` in `tools_config.py` maps platform → enabled toolsets. If absent, the toolset may default to disabled.

---

## Step 5 — Verify

```bash
hermes tools list
```

Expected output:
```
✓ enabled  smartthings  🏠 SmartThings
```

If it shows `✗ disabled smartthings`, run `hermes tools enable smartthings`.

**Restart Hermes** (exit + relaunch, or `/reset`) for schema changes to take effect.

---

## Debugging

| Symptom | Diagnosis |
|---|---|
| `hermes tools list` does not show smartthings | Check steps 2B + 3A. `CONFIGURABLE_TOOLSETS` must contain the entry. |
| Shows `✗ disabled smartthings` | Check step 4 — add to `platform_toolsets.cli` and run `hermes tools enable smartthings`. |
| Shows `✓ enabled` but tools not in schema | Check step 2A — tool names must be in `_HERMES_CORE_TOOLS`. |
| Import error in tool file | Check symlink path and `sys.path` / `HERMES_SMARTTHINGS_ROOT`. |
| `check_fn` raises instead of returns False | Hermes crashes during tool discovery. Wrap in try/except that returns False. |

---

## Generalizing to Other APIs

This same 4-file patching pattern works for any custom Hermes toolset:

1. `~/.hermes/hermes-agent/tools/<your_tool>.py` — call `registry.register()`
2. `~/.hermes/hermes-agent/toolsets.py` — add to `_HERMES_CORE_TOOLS` + `TOOLSETS`
3. `~/.hermes/hermes-agent/hermes_cli/tools_config.py` — add to `CONFIGURABLE_TOOLSETS` + `_DEFAULT_OFF_TOOLSETS`
4. `~/.hermes/config.yaml` — add to `platform_toolsets.cli`

See the `rest-api-tool-builder` skill for the upstream client/auth/logging pattern that feeds step 1.

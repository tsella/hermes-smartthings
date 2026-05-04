# Modular Tool Discovery for Hermes Agent

Hermes does NOT require patching core code to add tools.

## How it actually works

1. Files in `~/.hermes/hermes-agent/tools/*.py` are auto-imported at startup.
2. Any `.py` that calls `registry.register()` at module level is picked up.
3. The toolset is instantly available to the AI.
4. `hermes tools list` does NOT show it (TUI filters by known toolsets), but the AI can still call it.

## Minimal working example

Drop `~/.hermes/hermes-agent/tools/my_tool.py`:

```python
import json
from tools.registry import registry  # type: ignore

def my_hello_tool(name: str) -> str:
    return json.dumps({"greeting": f"Hello, {name}!"})

registry.register(
    name="my_hello_tool",
    toolset="hello",
    schema={
        "name": "my_hello_tool",
        "description": "Greet someone",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Name to greet"}},
            "required": ["name"],
        },
    },
    handler=lambda args, **kw: my_hello_tool(**args),
    check_fn=lambda: True,
)
```

Done. No edits to `toolsets.py` or `tools_config.py`.

## When to patch core Hermes

Only if you need:
- `hermes tools list` TUI to show the toolset
- The toolset to appear in the setup wizard
- A custom icon and description in the UI

This is cosmetic. The AI uses the tool regardless.

## Corollary: symlinked tool files work fine

```bash
ln -s ~/projects/my-plugin/tools/my_tool.py ~/.hermes/hermes-agent/tools/
```

The file is imported, `registry.register()` fires, tools appear.

## Corollary: use a proper src layout package, not flat modules

The tool file should import from an installable package, not rely on `sys.path.insert` or `HERMES_X_ROOT` env vars. Structure your project:

```
my-plugin/
├── pyproject.toml            # with src layout
├── README.md
└── src/
    └── my_plugin/
        ├── __init__.py
        └── core.py
```

Install it: `pip install -e ~/projects/my-plugin`

Then in `tools/my_tool.py`:
```python
from my_plugin.core import get_client
# No sys.path hacks. No env var fallbacks.
```

This removes an entire class of import-path and environment-configuration bugs.

## Pitfall: don't over-engineer

We proved this with the SmartThings integration: all 13 tools were available, tested, and working through auto-discovery. Then we wasted time patching core Hermes files for the TUI. That was unnecessary and would have broken on update. Revert core patches; keep the symlink.

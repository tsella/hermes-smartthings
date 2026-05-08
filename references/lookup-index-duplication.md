# Device-List Deduplication Fix

## Problem

The `_DeviceIndex.by_label` dict indexes each device under multiple fuzzy match keys for fast `resolve()` lookups:

- `"Samsung The Frame 43"` → stored under:
  - `"samsung the frame 43"`    (lowercase full)
  - `"samsungtheframe43"`       (no spaces)
  - `"samsung"` `"frame"` `"43"` (word parts)

When `_action_list()` iterated `by_label.values()`, the same device appeared **5 times** (10 devices → 37 entries).

## Solution

1. **Build a separate `self.devices` list** during `_refresh()` — deduplicated by `deviceId`, preserving API order.
2. **Keep `by_label` intact** as the fuzzy lookup index — only the list output changed.
3. **Switch `_action_list()`** from `by_label.values()` to `idx.devices`.

## Impact

| Before | After |
|---|---|
| `Samsung The Frame 43` ×5 | `Samsung The Frame 43` ×1 |
| `Music Frame` ×3 | `Music Frame` ×1 |
| 37 total entries | 10 unique devices |

No change to lookup behavior — `resolve("Samsung The Frame 43")` and `resolve_group("all tvs")` still work exactly as before.

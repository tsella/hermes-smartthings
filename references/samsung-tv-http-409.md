# Samsung TV HTTP 409 "invalid device state"

**Model:** Samsung TV (labeled "Samsung The Frame 65" in SmartThings, but user confirmed it is NOT a Frame TV)  
**Model number (OCF mnmo):** `QE65LS03BGUXSQ`  
**Date:** 2026-05-04

## Problem

`smartthings_send_command(device_id, "off")` (capability `switch`) returns:
```
HTTP 409: invalid device state
Code: ConflictError
```

The `switch` attribute reads `"on"` with a recent timestamp, so the TV is reporting as on.

## What was tried

| Approach | Result |
|---|---|
| `switch:off` | HTTP 409 — invalid device state |
| `samsungvd.remoteControl:createEvent` with POWER | 422 — `createEvent` is not a valid command for this capability |
| `execute` capability with Samsung DA payload (`x.com.samsung.da.data: off`) | HTTP 409 — invalid device state |
| `samsungvd.remoteControl:send HOME` | Not tried — suggested as next step to kick TV out of locked state |

## Key discovery

The `samsungvd.remoteControl` capability only supports these keys: UP, DOWN, LEFT, RIGHT, OK, BACK, EXIT, MENU, HOME, MUTE, PLAY, PAUSE, STOP, REWIND, FF, PLAY_BACK, SOURCE. **No POWER key exists in the enum.**

## Working theory

Samsung TVs sometimes enter a firmware state where the OCF state machine rejects `switch:off`. This is NOT Art Mode (confirmed by user: TV is not a Frame TV). The 409 may indicate the TV's internal power state is transitional or locked.

## Recommended next attempts for future 409s

1. Send `samsungvd.remoteControl:send` with `"HOME"` or `"EXIT"` to reset any modal/app state
2. Wait 2-3 seconds
3. Retry `switch:off`
4. If still 409, ask user to confirm via Samsung SmartThings mobile app — if the app also can't turn it off, it's a Samsung-side firmware issue

## Reference

- Capability schema for `samsungvd.remoteControl`: `GET /capabilities/samsungvd.remoteControl/1`

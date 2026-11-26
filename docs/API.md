# Local API observations

Device: `doorUnitBox_v2`, type `gateBox`, hardware `W-dU-2.0`, firmware `0.1060`, API level `20230102`, addon API level `20220713`.

The `/info` response advertises switch addons 0–2 (LED 1–3), settingsSwitch addon 3 (Button), sensor addon 4 (lockSensor S2). Discover addon IDs dynamically rather than assuming these IDs for all devices.

`GET /state` (also `/state/extended`) contains `gate.currentPos`, plus an `addons` array containing relay states, `defaultForTime`, the handle setting and S2 sensor state.

Observed local commands for each advertised lighting output: `GET /a/{id}/s/0`, `GET /a/{id}/s/1`, `GET /a/{id}/s/1/forTime/{seconds}/ns/0`. Timed lighting independently tested for 10, 4 and 5 seconds respectively. Handle setting uses `GET /a/{id}/s/0` or `/s/1` for the settingsSwitch addon. The setting path is `settings/gate/conditionalAction/execute`.

S1 is read from `gate.currentPos`; 0 maps to locked and 100 maps to unlocked. S1 changes with the mechanical key on the tested installation; this does not establish physical door position. S2 is read from the separate sensor addon value; 0 maps to unlocked based on wBox display, but the active transition and polarity have not been independently confirmed. Wiring varies by installation. Never infer that the door leaf is closed merely from a bolt sensor.

The release button uses the native open operation. It is disabled by default; hardware verification is pending.

The documented behavior applies to firmware 0.1060.

## Physical inputs and actions

Verified on W-dU-2.0 firmware 0.1060:

- `GET /api/input/state` returns `{"inputs":[{"input":0,"state":0},{"input":1,"state":0}]}`. The two entries report physical input levels; their transitions during a button press and the minimum pulse length have not yet been measured.
- `GET /api/actions/state` returns an `actions` array, `itemsLimit: 30`, and field constraints.
- Input 0 corresponds to IN1 (bell); input 1 corresponds to IN2 (handle). Trigger type 4 is the rising-edge trigger.
- Existing native action: input 1, trigger type 4, action type 100, parameter `http://localhost/s/p/conditional`. This is the conditional local release operation, not evidence that type 100 is a general-purpose URL action.
- Action type 52 was observed for a notification. Action type 50 was observed when saving a URL action in wBox; the actual outbound request has not yet been captured.
- Empty slots have action type and trigger type 0 and an empty parameter. `lastCall.timeElapsedS` is runtime metadata; -1 was observed for unused actions.

### Writing one action

A local HTTP capture of wBox confirmed `POST /api/actions/set` with `Content-Type: application/json`. The following example retains the observed request structure, with the destination replaced by a documentation-only address:

```json
{
  "action": {
    "id": 2,
    "name": "HA - HANDLE TEST",
    "input": 0,
    "triggerType": 4,
    "actionType": 50,
    "lastCall": {"timeElapsedS": -1},
    "triggerParam": 0,
    "param": "http://192.0.2.1:8123",
    "throttleS": 0,
    "intervalS": 0
  }
}
```

The device returned HTTP 200 with an `action` object; a subsequent GET confirmed that only slot 2 changed. The response omitted `throttleS`. Whether the request can omit runtime metadata or other fields has not been tested. Despite the test action's name, its input was 0 (IN1).

Preserve native conditional release and other user actions. Any integration-managed URL actions should be separately allocated and verified by reading back their configuration. Outbound event delivery, authentication, and handling of short or repeated input pulses still require testing. Do not interpret an unknown handle setting as permission to unlock.

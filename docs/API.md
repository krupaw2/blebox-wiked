# Local API observations

Device: `doorUnitBox_v2`, type `gateBox`, hardware `W-dU-2.0`, firmware `0.1060`, API level `20230102`, addon API level `20220713`.

The `/info` response advertises switch addons 0–2 (LED 1–3), settingsSwitch addon 3 (Button), sensor addon 4 (lockSensor S2). Discover addon IDs dynamically rather than assuming these IDs for all devices.

`GET /state` (also `/state/extended`) contains `gate.currentPos`, plus an `addons` array containing relay states, `defaultForTime`, the handle setting and S2 sensor state.

Observed local commands for each advertised lighting output: `GET /a/{id}/s/0`, `GET /a/{id}/s/1`, `GET /a/{id}/s/1/forTime/{seconds}/ns/0`. Timed lighting independently tested for 10, 4 and 5 seconds respectively. Handle setting uses `GET /a/{id}/s/0` or `/s/1` for the settingsSwitch addon. The setting path is `settings/gate/conditionalAction/execute`.

S1 is read from `gate.currentPos`; 0 maps to locked and 100 maps to unlocked. S1 changes with the mechanical key on the tested installation; this does not establish physical door position. S2 is read from the separate sensor addon value; 0 maps to unlocked based on wBox display, but the active transition and polarity have not been independently confirmed. Wiring varies by installation. Never infer that the door leaf is closed merely from a bolt sensor.

The release button uses the native open operation. It is disabled by default; hardware verification is pending.

The documented behavior applies to firmware 0.1060.

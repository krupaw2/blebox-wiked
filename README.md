# WIKĘD Smart 2.0 for Home Assistant

Extension of the BleBox integration for WIKĘD Smart 2.0 door controllers (`doorUnitBox_v2`).

## Features

- Three independent LED outputs.
- Timed lighting with an individual duration of 1–3600 seconds per output.
- Handle button enable/disable.
- Separate S1 and S2 binary sensors.
- Door release button (disabled by default).
- Existing BleBox cover and firmware update entities.

## Compatibility

Installed on Home Assistant Core 2026.11.3 with W-dU-2.0 hardware, firmware 0.1060. S1 state changes verified in Home Assistant. LED switching and timed commands verified in wBox traffic. HA lighting controls, S2 transitions and the release button still require hardware verification.

## Installation

The installer copies the matching BleBox integration to `/config/custom_components/blebox` and adds WIKĘD support. Existing unrelated custom integrations are not overwritten.

Back up Home Assistant before installation. Python 3 is required in the terminal. On the Alpine-based Terminal & SSH add-on, if Python is missing:

```sh
apk add --no-cache python3
```

Copy `blebox_wiked_install_0.1.2.py` to `/config` and run:

```sh
python3 /config/blebox_wiked_install_0.1.2.py && ha core check && ha core restart
```

Keep the existing cover entity until the release button is verified. S1 and S2 report input states, not the physical position of the door.

## Updates

```sh
python3 /config/blebox_wiked_install_0.1.2.py --upgrade && ha core check && ha core restart
```

The installer backs up the previous overlay. The overlay persists across Home Assistant updates and takes precedence over the built-in BleBox integration. Check compatibility after Core updates. HACS installation is not supported in this version.

## Removal

```sh
python3 /config/blebox_wiked_install_0.1.2.py --remove && ha core check && ha core restart
```

The removed overlay is saved in `/config/blebox_wiked_removed`. Removal stops if this directory already exists. The built-in integration is loaded on restart; custom entities may remain in the entity registry.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

Tests cover parsing, input state mapping, payload syntax and overwrite protection. They do not require Home Assistant or physical devices.

## Links

- [Local API documentation](docs/API.md)
- [BleBox issue #210](https://github.com/blebox/blebox_uniapi/issues/210)


## Experimental input events (0.1.3)

The `feature/input-events` branch adds a candidate installer, `blebox_wiked_install_0.1.3.py`. It retains the existing controls and adds local HA event entities for IN1 and IN2. The **Configure input events** button explicitly provisions two independent URL actions in free device slots; it does not replace existing user actions or send a door release command. Setup does not write device configuration automatically. The configured webhooks use random persistent identifiers and accept only local HTTP GET requests.

IN1 reports `doorbell`; IN2 reports `doorbell` when the handle is disabled, `pressed` when enabled, or `pressed_unknown` if its setting cannot be read. The classification is based on the fresh setting at reception, not an atomic snapshot at the physical input edge. The native conditional release remains independent of HA.

This is a hardware-test candidate, not a released version. HTTP delivery, installed HA compatibility, action URL length and both handle modes still require validation. Back up HA and the device action inventory before opting in. Repeated configuration reuses only actions belonging to this entry. Removing the overlay does not remove provisioned device actions; remove only the two integration-managed actions using wBox if retiring the feature. An old test action created separately in wBox is not managed by the integration.

The offline regression tests do not exercise an actual device or HA runtime.

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

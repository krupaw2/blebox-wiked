#!/usr/bin/env python3
"""Install a version-matched BleBox overlay. Never edit the HA container."""
import argparse
import ast
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request

PAYLOAD = '"""WIKĘD Smart 2 support for the native BleBox integration."""\nfrom datetime import timedelta\nimport asyncio\nimport logging\n\nfrom blebox_uniapi.error import Error, UnauthorizedRequest\nfrom homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity\nfrom homeassistant.components.button import ButtonEntity\nfrom homeassistant.components.light import ColorMode, LightEntity\nfrom homeassistant.components.number import RestoreNumber\nfrom homeassistant.components.switch import SwitchEntity\nfrom homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError\nfrom homeassistant.helpers.device_registry import DeviceInfo\nfrom homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed\n\nfrom .const import DOMAIN\n\n_LOGGER = logging.getLogger(__name__)\nPRODUCT = "doorUnitBox_v2"\n\n\ndef get_addons(device):\n    """Accept only the advertised, supported addon types, never guess output IDs."""\n    result = {}\n    for a in device.get("addons", []):\n        i = a.get("id")\n        if type(i) is not int or i < 0:\n            continue\n        if a.get("type") in ("switch", "settingsSwitch", "sensor"):\n            result[i] = a\n    return result\n\n\ndef state_map(response):\n    if not isinstance(response, dict) or not isinstance(response.get("addons"), list):\n        raise ValueError("WIKED response does not contain addons")\n    data = {a["id"]: a for a in response["addons"] if isinstance(a, dict) and type(a.get("id")) is int}\n    data["gate"] = response.get("gate", {})\n    return data\n\n\ndef bit(data, key, field):\n    value = data.get(key, {}).get(field)\n    return value == 1 if type(value) is int and value in (0, 1) else None\n\n\nclass WikedCoordinator(DataUpdateCoordinator):\n    def __init__(self, hass, entry, native, api_host, device):\n        super().__init__(hass, _LOGGER, name=f"{DOMAIN} WIKED {native.box.unique_id}",\n                         config_entry=entry, update_interval=timedelta(seconds=5))\n        self.native = native\n        self.api_host = api_host\n        self.addons = get_addons(device)\n        self.device = device\n        self.io_lock = asyncio.Lock()\n        self.durations = {}\n\n    async def _async_update_data(self):\n        try:\n            async with self.io_lock:\n                return state_map(await self.api_host.async_api_get("/state"))\n        except UnauthorizedRequest as err:\n            raise ConfigEntryAuthFailed from err\n        except (Error, ValueError, OSError, asyncio.TimeoutError) as err:\n            raise UpdateFailed(f"WIKED: {err}") from err\n\n    def duration_for(self, addon_id):\n        if addon_id not in self.durations:\n            value = (self.data or {}).get(addon_id, {}).get("relay", {}).get("defaultForTime")\n            self.durations[addon_id] = value if type(value) is int and 1 <= value <= 3600 else 60\n        return self.durations[addon_id]\n\n    async def command(self, addon_id, on, seconds=None):\n        kind = self.addons.get(addon_id, {}).get("type")\n        if kind not in ("switch", "settingsSwitch"):\n            raise HomeAssistantError("Unsupported WIKED output")\n        path = f"/a/{addon_id}/s/{int(on)}"\n        if seconds is not None:\n            if kind != "switch" or not on or type(seconds) is not int or not 1 <= seconds <= 3600:\n                raise HomeAssistantError("Invalid WIKED lighting duration (1-3600 s)")\n            path += f"/forTime/{seconds}/ns/0"\n        try:\n            async with self.io_lock:\n                data = state_map(await self.api_host.async_api_get(path))\n                if addon_id not in data:\n                    raise ValueError("Command response missing target addon")\n                group, field = ("relay", "state") if kind == "switch" else ("settingsSwitch", "value")\n                if bit(data[addon_id], group, field) is not on:\n                    raise ValueError("Device did not confirm requested state")\n                self.async_set_updated_data(data)\n        except (Error, ValueError, OSError, asyncio.TimeoutError) as err:\n            await self.async_request_refresh()\n            raise HomeAssistantError(f"WIKED command not confirmed: {err}") from err\n\n\nasync def async_prepare(hass, entry, native, api_host):\n    """Only override exact WIKED product, leave every other BleBox unchanged."""\n    if native.box.type != "gateBox":\n        return\n    try:\n        response = await api_host.async_api_get("/info")\n        device = response.get("device", {})\n        if device.get("product") != PRODUCT:\n            return\n        if device.get("id") != native.box.unique_id:\n            raise ValueError("WIKED device identity mismatch")\n        coordinator = WikedCoordinator(hass, entry, native, api_host, device)\n        if not coordinator.addons:\n            raise ValueError("WIKED device has no supported addons")\n        await coordinator.async_config_entry_first_refresh()\n        native.wiked = coordinator\n    except (Error, ValueError, AttributeError, OSError, asyncio.TimeoutError) as err:\n        # Do not silently replace working native control if discovery fails.\n        _LOGGER.warning("WIKED extension not activated for %s: %s", native.box.name, err)\n\n\nclass WikedEntity(CoordinatorEntity):\n    _attr_has_entity_name = True\n\n    def __init__(self, coordinator, suffix, name):\n        super().__init__(coordinator)\n        box = coordinator.native.box\n        self._attr_unique_id = f"{box.unique_id}_wiked_{suffix}"\n        self._attr_name = name\n        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, box.unique_id)},\n            manufacturer="WIKĘD / BleBox", model="WIKĘD Smart 2.0",\n            name=box.name, sw_version=box.firmware_version,\n            configuration_url=f"http://{box.address}")\n\n\nclass AddonEntity(WikedEntity):\n    def __init__(self, coordinator, addon_id):\n        self.addon_id = addon_id\n        name = coordinator.addons[addon_id].get("name") or f"Addon {addon_id}"\n        super().__init__(coordinator, f"addon_{addon_id}", name)\n\n    @property\n    def addon_state(self):\n        return (self.coordinator.data or {}).get(self.addon_id, {})\n\n    @property\n    def available(self):\n        return super().available and self.addon_id in (self.coordinator.data or {})\n\n\nclass WikedLight(AddonEntity, LightEntity):\n    _attr_supported_color_modes = {ColorMode.ONOFF}\n    _attr_color_mode = ColorMode.ONOFF\n\n    @property\n    def is_on(self):\n        return bit(self.addon_state, "relay", "state")\n\n    @property\n    def extra_state_attributes(self):\n        return {"default_duration": self.addon_state.get("relay", {}).get("defaultForTime")}\n\n    async def async_turn_on(self, **kwargs):\n        await self.coordinator.command(self.addon_id, True)\n\n    async def async_turn_off(self, **kwargs):\n        await self.coordinator.command(self.addon_id, False)\n\n\nclass WikedSettingsSwitch(AddonEntity, SwitchEntity):\n    _attr_icon = "mdi:gesture-tap-button"\n    _attr_name = "Handle button enabled"\n\n    def __init__(self, coordinator, addon_id):\n        super().__init__(coordinator, addon_id)\n        self._attr_name = "Przycisk pochwytu"\n\n    @property\n    def is_on(self):\n        return bit(self.addon_state, "settingsSwitch", "value")\n\n    async def async_turn_on(self, **kwargs):\n        await self.coordinator.command(self.addon_id, True)\n\n    async def async_turn_off(self, **kwargs):\n        await self.coordinator.command(self.addon_id, False)\n\n\nclass WikedBolt(AddonEntity, BinarySensorEntity):\n    _attr_device_class = BinarySensorDeviceClass.LOCK\n\n    def __init__(self, coordinator, addon_id):\n        super().__init__(coordinator, addon_id)\n        self._attr_name = "S2"\n\n    @property\n    def extra_state_attributes(self):\n        return {"input": "S2", "raw_value": self.addon_state.get("sensor", {}).get("value")}\n\n    @property\n    def is_on(self):\n        # HA LOCK binary sensor: ON = unlocked. S2=0 is shown open in wBox.\n        locked = bit(self.addon_state, "sensor", "value")\n        return None if locked is None else not locked\n\n\nclass WikedS1(WikedEntity, BinarySensorEntity):\n    _attr_device_class = BinarySensorDeviceClass.LOCK\n\n    def __init__(self, coordinator):\n        super().__init__(coordinator, "s1", "S1")\n\n    @property\n    def raw_position(self):\n        gate = (self.coordinator.data or {}).get("gate")\n        return gate.get("currentPos") if isinstance(gate, dict) else None\n\n    @property\n    def extra_state_attributes(self):\n        return {"input": "S1", "raw_current_pos": self.raw_position}\n\n    @property\n    def is_on(self):\n        pos = self.raw_position\n        if type(pos) is int and pos in (0, 100):\n            return pos == 100\n        return None\n\n\nclass WikedRelease(WikedEntity, ButtonEntity):\n    _attr_icon = "mdi:door-open"\n    # Opt-in until the existing open operation is verified on the actual door.\n    _attr_entity_registry_enabled_default = False\n\n    def __init__(self, coordinator, feature):\n        super().__init__(coordinator, "release", "Elektrozaczep")\n        self.feature = feature\n\n    async def async_press(self):\n        try:\n            async with self.coordinator.io_lock:\n                await self.feature.async_open()\n        except Error as err:\n            raise HomeAssistantError(f"WIKED release failed: {err}") from err\n        finally:\n            await self.coordinator.async_request_refresh()\n\n\nclass WikedDuration(WikedEntity, RestoreNumber):\n    """HA-local duration; never changes the device\'s persistent settings."""\n    _attr_icon = "mdi:timer-cog-outline"\n    _attr_native_min_value = 1\n    _attr_native_max_value = 3600\n    _attr_native_step = 1\n    _attr_native_unit_of_measurement = "s"\n\n    def __init__(self, coordinator, addon_id):\n        self.addon_id = addon_id\n        name = coordinator.addons[addon_id].get("name") or f"Addon {addon_id}"\n        super().__init__(coordinator, f"duration_{addon_id}", f"{name} czas świecenia")\n\n    @property\n    def native_value(self):\n        return self.coordinator.duration_for(self.addon_id)\n\n    async def async_added_to_hass(self):\n        await super().async_added_to_hass()\n        data = await self.async_get_last_number_data()\n        if data is not None and data.native_value is not None:\n            value = data.native_value\n            if 1 <= value <= 3600 and int(value) == value:\n                self.coordinator.durations[self.addon_id] = int(value)\n\n    async def async_set_native_value(self, value):\n        if not 1 <= value <= 3600 or int(value) != value:\n            raise HomeAssistantError("Invalid WIKED lighting duration (1-3600 s)")\n        self.coordinator.durations[self.addon_id] = int(value)\n        self.async_write_ha_state()\n\n\nclass WikedTimedLight(WikedEntity, ButtonEntity):\n    _attr_icon = "mdi:timer-outline"\n\n    def __init__(self, coordinator, addon_id):\n        self.addon_id = addon_id\n        name = coordinator.addons[addon_id].get("name") or f"Addon {addon_id}"\n        super().__init__(coordinator, f"timed_{addon_id}", f"{name} czasowo")\n\n    @property\n    def duration(self):\n        return self.coordinator.duration_for(self.addon_id)\n\n    @property\n    def available(self):\n        return super().available and "relay" in (self.coordinator.data or {}).get(self.addon_id, {})\n\n    async def async_press(self):\n        await self.coordinator.command(self.addon_id, True, self.duration)\n\n\ndef entities_for(coordinator, platform):\n    """Create only entities backed by actual advertised features."""\n    entities = []\n    for i, info in coordinator.addons.items():\n        kind = info["type"]\n        state = (coordinator.data or {}).get(i, {})\n        if platform == "light" and kind == "switch" and "relay" in state:\n            entities.append(WikedLight(coordinator, i))\n        elif platform == "switch" and kind == "settingsSwitch" and state.get("settingsSwitch", {}).get("path") == "settings/gate/conditionalAction/execute":\n            entities.append(WikedSettingsSwitch(coordinator, i))\n        elif platform == "binary_sensor" and kind == "sensor" and state.get("sensor", {}).get("type") == "lock":\n            entities.append(WikedBolt(coordinator, i))\n        elif platform == "button" and kind == "switch" and "relay" in state:\n            entities.append(WikedTimedLight(coordinator, i))\n        elif platform == "number" and kind == "switch" and "relay" in state:\n            entities.append(WikedDuration(coordinator, i))\n    if platform == "binary_sensor":\n        entities.append(WikedS1(coordinator))\n    if platform == "button":\n        covers = coordinator.native.box.features.get("covers", [])\n        if len(covers) == 1:\n            entities.append(WikedRelease(coordinator, covers[0]))\n    return entities\n'


def native_source(target, version):
    # Prefer a copy of the actual installed integration, including translations.
    if shutil.which('docker'):
        result = subprocess.run(['docker','cp','homeassistant:/usr/src/homeassistant/homeassistant/components/blebox/.',str(target)],capture_output=True,text=True)
        if result.returncode == 0 and (target/'manifest.json').exists():
            return 'installed Core (docker cp)'
    if not re.fullmatch(r'20\d\d\.\d{1,2}\.\d+', version):
        raise RuntimeError('Expected exact stable HA Core version, e.g. 2026.11.2')
    def download_dir(rel, dest):
        url = f'https://api.github.com/repos/home-assistant/core/contents/{rel}?ref={version}'
        req = urllib.request.Request(url, headers={'User-Agent':'WIKED-BleBox-Installer','Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(req, timeout=30) as r:
            entries = json.load(r)
        dest.mkdir(parents=True, exist_ok=True)
        for e in entries:
            path = dest/e['name']
            if e['type'] == 'dir':
                download_dir(e['path'], path)
            elif e['type'] == 'file':
                with urllib.request.urlopen(e['download_url'], timeout=30) as r:
                    path.write_bytes(r.read())
    download_dir('homeassistant/components/blebox', target)
    return f'official Core tag {version}'


def patch(target, version):
    init = target/'__init__.py'
    source = init.read_text(encoding='utf-8')
    pattern = r'(?m)^(\s*)await hass\.config_entries\.async_forward_entry_setups\(entry, PLATFORMS\)\s*$'
    # Fail closed if upstream integration layout differs.
    if not all(x in source for x in ('api_host = ApiHost(', 'coordinator = BleBoxCoordinator(', 'entry.runtime_data = coordinator')):
        raise RuntimeError('Unsupported native BleBox setup layout; nothing installed')
    source, n = re.subn(pattern, lambda m: f'{m[1]}from .wiked import async_prepare\n{m[1]}await async_prepare(hass, entry, coordinator, api_host)\n{m[1]}await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)\n', source)
    if n != 1:
        raise RuntimeError('Cannot locate unique platform setup hook; nothing installed')
    if 'Platform.NUMBER' not in source:
        source, n = re.subn(r'(?m)^(PLATFORMS\s*=\s*\[)', r'\1\n    Platform.NUMBER,', source)
        if n != 1:
            raise RuntimeError('Cannot locate native platform list')
    init.write_text(source,encoding='utf-8')
    for platform in ('cover','light','switch','binary_sensor','button'):
        file = target/f'{platform}.py'
        source = file.read_text(encoding='utf-8')
        # The upstream functions have stable signature; guard actual source before wrapping.
        if not re.search(r'async def async_setup_entry\(', source) or 'runtime_data' not in source:
            raise RuntimeError(f'Unsupported {platform} setup layout')
        source += f'''\n\n# WIKED extension: native behavior retained for other products.\n_native_async_setup_entry = async_setup_entry\n\nasync def async_setup_entry(hass, config_entry, async_add_entities):\n    wiked = getattr(config_entry.runtime_data, "wiked", None)\n    if wiked is None:\n        return await _native_async_setup_entry(hass, config_entry, async_add_entities)\n'''
        if platform != 'cover':
            source += f'    from .wiked import entities_for\n    async_add_entities(entities_for(wiked, "{platform}"))\n'
        else:
            # Transitional: keep existing cover working until replacement tested.
            source += '    return await _native_async_setup_entry(hass, config_entry, async_add_entities)\n'
        file.write_text(source,encoding='utf-8')
    number = target/'number.py'
    if number.exists():
        number_source = number.read_text(encoding='utf-8')
        if not re.search(r'async def async_setup_entry\(', number_source):
            raise RuntimeError('Unsupported number setup layout')
        number_source += "\n\n_native_async_setup_entry = async_setup_entry\n\nasync def async_setup_entry(hass, config_entry, async_add_entities):\n    wiked = getattr(config_entry.runtime_data, 'wiked', None)\n    if wiked is None:\n        return await _native_async_setup_entry(hass, config_entry, async_add_entities)\n    from .wiked import entities_for\n    async_add_entities(entities_for(wiked, 'number'))\n"
    else:
        number_source = "\"\"\"WIKED local lighting durations.\"\"\"\n\nasync def async_setup_entry(hass, config_entry, async_add_entities):\n    wiked = getattr(config_entry.runtime_data, 'wiked', None)\n    if wiked is not None:\n        from .wiked import entities_for\n        async_add_entities(entities_for(wiked, 'number'))\n"
    number.write_text(number_source,encoding='utf-8')
    compile(number_source,'number.py','exec')
    # Native update platform stays untouched; copy full native component and config flow.
    (target/'wiked.py').write_text(PAYLOAD,encoding='utf-8')
    manifest_path = target/'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['version'] = '0.1.2'
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    if (target/'strings.json').exists() and not (target/'translations'/'en.json').exists():
        (target/'translations').mkdir(exist_ok=True)
        shutil.copy2(target/'strings.json',target/'translations'/'en.json')
    # HA uses Python >=3.13; older terminal Python may not parse native PEP695.
    ast.parse(PAYLOAD)
    compile(PAYLOAD,'wiked.py','exec')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--config',default='/config')
    p.add_argument('--version')
    p.add_argument('--native-source',type=Path,help='Exact installed BleBox directory, if available')
    p.add_argument('--remove',action='store_true')
    p.add_argument('--upgrade',action='store_true',help='Replace only a previously installed WIKED overlay')
    a=p.parse_args()
    config=Path(a.config)
    if not (config/'configuration.yaml').exists():
        raise RuntimeError('Not an HA config directory')
    custom=config/'custom_components'; dest=custom/'blebox'; marker=dest/'.wiked-overlay'
    if a.remove:
        if not marker.is_file():
            raise RuntimeError('Refusing to remove a non-WIKED integration')
        # Preserve a copy outside custom_components so rollback does not lose files.
        backup=config/'blebox_wiked_removed'
        if backup.exists():
            raise RuntimeError(f'Backup already exists: {backup}')
        dest.rename(backup)
        print(f'Removed overlay; backup: {backup}. Restart Core to restore native integration.')
        return
    if dest.exists() and not (a.upgrade and marker.is_file()):
        raise RuntimeError(f'{dest} already exists; refusing to overwrite it. Use --upgrade only for WIKED overlay.')
    version=a.version
    if not version:
        try:
            info=json.loads(subprocess.check_output(['ha','core','info','--raw-json'],text=True))
            version=info.get('data',info)['version']
        except Exception as ex:
            if not a.native_source:
                raise RuntimeError('Cannot determine HA Core version; use --version EXACT_VERSION') from ex
            version='local'
    custom.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='wiked-',dir=config) as tmp:
        stage=Path(tmp)/'blebox'; stage.mkdir()
        if a.native_source:
            shutil.copytree(a.native_source,stage,dirs_exist_ok=True)
            origin=str(a.native_source)
        else:
            origin=native_source(stage,version)
        patch(stage,version)
        (stage/'.wiked-overlay').write_text(f'{version}\n{origin}\n')
        if dest.exists():
            backup = Path(tempfile.mkdtemp(prefix='blebox_wiked_backup-',dir=config))/'blebox'
            dest.rename(backup)
            try:
                stage.rename(dest)
            except BaseException:
                backup.rename(dest)
                raise
            print(f'Previous overlay backup: {backup}')
        else:
            stage.rename(dest)
    print(f'Installed WIKED overlay from {origin} into {dest}.')
    print('No device commands were sent. Run ha core check, then restart Core if check passes.')
    print('Old cover remains for migration; disable it manually after validating the new button.')

if __name__=='__main__':
    main()

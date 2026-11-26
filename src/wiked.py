"""WIKĘD Smart 2 support for the native BleBox integration."""
from datetime import timedelta
import asyncio
import logging

from blebox_uniapi.error import Error, UnauthorizedRequest
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.components.number import RestoreNumber
from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PRODUCT = "doorUnitBox_v2"


def get_addons(device):
    """Accept only the advertised, supported addon types, never guess output IDs."""
    result = {}
    for a in device.get("addons", []):
        i = a.get("id")
        if type(i) is not int or i < 0:
            continue
        if a.get("type") in ("switch", "settingsSwitch", "sensor"):
            result[i] = a
    return result


def state_map(response):
    if not isinstance(response, dict) or not isinstance(response.get("addons"), list):
        raise ValueError("WIKED response does not contain addons")
    data = {a["id"]: a for a in response["addons"] if isinstance(a, dict) and type(a.get("id")) is int}
    data["gate"] = response.get("gate", {})
    return data


def bit(data, key, field):
    value = data.get(key, {}).get(field)
    return value == 1 if type(value) is int and value in (0, 1) else None


class WikedCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, native, api_host, device):
        super().__init__(hass, _LOGGER, name=f"{DOMAIN} WIKED {native.box.unique_id}",
                         config_entry=entry, update_interval=timedelta(seconds=5))
        self.native = native
        self.api_host = api_host
        self.addons = get_addons(device)
        self.device = device
        self.io_lock = asyncio.Lock()
        self.durations = {}

    async def _async_update_data(self):
        try:
            async with self.io_lock:
                return state_map(await self.api_host.async_api_get("/state"))
        except UnauthorizedRequest as err:
            raise ConfigEntryAuthFailed from err
        except (Error, ValueError, OSError, asyncio.TimeoutError) as err:
            raise UpdateFailed(f"WIKED: {err}") from err

    def duration_for(self, addon_id):
        if addon_id not in self.durations:
            value = (self.data or {}).get(addon_id, {}).get("relay", {}).get("defaultForTime")
            self.durations[addon_id] = value if type(value) is int and 1 <= value <= 3600 else 60
        return self.durations[addon_id]

    async def command(self, addon_id, on, seconds=None):
        kind = self.addons.get(addon_id, {}).get("type")
        if kind not in ("switch", "settingsSwitch"):
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="wiked_unsupported_output")
        path = f"/a/{addon_id}/s/{int(on)}"
        if seconds is not None:
            if kind != "switch" or not on or type(seconds) is not int or not 1 <= seconds <= 3600:
                raise HomeAssistantError(translation_domain=DOMAIN, translation_key="wiked_invalid_duration")
            path += f"/forTime/{seconds}/ns/0"
        try:
            async with self.io_lock:
                data = state_map(await self.api_host.async_api_get(path))
                if addon_id not in data:
                    raise ValueError("Command response missing target addon")
                group, field = ("relay", "state") if kind == "switch" else ("settingsSwitch", "value")
                if bit(data[addon_id], group, field) is not on:
                    raise ValueError("Device did not confirm requested state")
                self.async_set_updated_data(data)
        except (Error, ValueError, OSError, asyncio.TimeoutError) as err:
            await self.async_request_refresh()
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="wiked_command_failed") from err


async def async_prepare(hass, entry, native, api_host):
    """Only override exact WIKED product, leave every other BleBox unchanged."""
    if native.box.type != "gateBox":
        return
    try:
        response = await api_host.async_api_get("/info")
        device = response.get("device", {})
        if device.get("product") != PRODUCT:
            return
        if device.get("id") != native.box.unique_id:
            raise ValueError("WIKED device identity mismatch")
        coordinator = WikedCoordinator(hass, entry, native, api_host, device)
        if not coordinator.addons:
            raise ValueError("WIKED device has no supported addons")
        await coordinator.async_config_entry_first_refresh()
        native.wiked = coordinator
    except (Error, ValueError, AttributeError, OSError, asyncio.TimeoutError) as err:
        # Do not silently replace working native control if discovery fails.
        _LOGGER.warning("WIKED extension not activated for %s: %s", native.box.name, err)


class WikedEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, suffix, name=None, *, translation_key=None, placeholders=None):
        super().__init__(coordinator)
        box = coordinator.native.box
        self._attr_unique_id = f"{box.unique_id}_wiked_{suffix}"
        # HA gives an explicitly set _attr_name (even None) priority over translations.
        if translation_key is None:
            if name is None:
                raise ValueError("WIKED entity requires a name or translation key")
            self._attr_name = name
        else:
            self._attr_translation_key = translation_key
        if placeholders is not None:
            self._attr_translation_placeholders = placeholders
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, box.unique_id)},
            manufacturer="WIKĘD / BleBox", model="WIKĘD Smart 2.0",
            name=box.name, sw_version=box.firmware_version,
            configuration_url=f"http://{box.address}")


class AddonEntity(WikedEntity):
    def __init__(self, coordinator, addon_id, *, translation_key=None):
        self.addon_id = addon_id
        name = coordinator.addons[addon_id].get("name") or f"Addon {addon_id}"
        super().__init__(coordinator, f"addon_{addon_id}", name, translation_key=translation_key)

    @property
    def addon_state(self):
        return (self.coordinator.data or {}).get(self.addon_id, {})

    @property
    def available(self):
        return super().available and self.addon_id in (self.coordinator.data or {})


class WikedLight(AddonEntity, LightEntity):
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF

    @property
    def is_on(self):
        return bit(self.addon_state, "relay", "state")

    @property
    def extra_state_attributes(self):
        return {"default_duration": self.addon_state.get("relay", {}).get("defaultForTime")}

    async def async_turn_on(self, **kwargs):
        await self.coordinator.command(self.addon_id, True)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.command(self.addon_id, False)


class WikedSettingsSwitch(AddonEntity, SwitchEntity):
    _attr_icon = "mdi:gesture-tap-button"

    def __init__(self, coordinator, addon_id):
        super().__init__(coordinator, addon_id, translation_key="wiked_handle")

    @property
    def is_on(self):
        return bit(self.addon_state, "settingsSwitch", "value")

    async def async_turn_on(self, **kwargs):
        await self.coordinator.command(self.addon_id, True)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.command(self.addon_id, False)


class WikedBolt(AddonEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.LOCK

    def __init__(self, coordinator, addon_id):
        super().__init__(coordinator, addon_id, translation_key="wiked_s2")

    @property
    def extra_state_attributes(self):
        return {"input": "S2", "raw_value": self.addon_state.get("sensor", {}).get("value")}

    @property
    def is_on(self):
        # HA LOCK binary sensor: ON = unlocked. S2=0 is shown open in wBox.
        locked = bit(self.addon_state, "sensor", "value")
        return None if locked is None else not locked


class WikedS1(WikedEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.LOCK

    def __init__(self, coordinator):
        super().__init__(coordinator, "s1", translation_key="wiked_s1")

    @property
    def raw_position(self):
        gate = (self.coordinator.data or {}).get("gate")
        return gate.get("currentPos") if isinstance(gate, dict) else None

    @property
    def extra_state_attributes(self):
        return {"input": "S1", "raw_current_pos": self.raw_position}

    @property
    def is_on(self):
        pos = self.raw_position
        if type(pos) is int and pos in (0, 100):
            return pos == 100
        return None


class WikedRelease(WikedEntity, ButtonEntity):
    _attr_icon = "mdi:door-open"
    # Explicit opt-in for physical access control.
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, feature):
        super().__init__(coordinator, "release", translation_key="wiked_release")
        self.feature = feature

    async def async_press(self):
        try:
            async with self.coordinator.io_lock:
                await self.feature.async_open()
        except Error as err:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="wiked_release_failed") from err
        finally:
            await self.coordinator.async_request_refresh()


class WikedDuration(WikedEntity, RestoreNumber):
    """HA-local duration; never changes the device's persistent settings."""
    _attr_icon = "mdi:timer-cog-outline"
    _attr_native_min_value = 1
    _attr_native_max_value = 3600
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "s"

    def __init__(self, coordinator, addon_id):
        self.addon_id = addon_id
        name = coordinator.addons[addon_id].get("name") or f"Addon {addon_id}"
        super().__init__(coordinator, f"duration_{addon_id}", translation_key="wiked_duration",
                         placeholders={"output": name})

    @property
    def native_value(self):
        return self.coordinator.duration_for(self.addon_id)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        data = await self.async_get_last_number_data()
        if data is not None and data.native_value is not None:
            value = data.native_value
            if 1 <= value <= 3600 and int(value) == value:
                self.coordinator.durations[self.addon_id] = int(value)

    async def async_set_native_value(self, value):
        if not 1 <= value <= 3600 or int(value) != value:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="wiked_invalid_duration")
        self.coordinator.durations[self.addon_id] = int(value)
        self.async_write_ha_state()


class WikedTimedLight(WikedEntity, ButtonEntity):
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator, addon_id):
        self.addon_id = addon_id
        name = coordinator.addons[addon_id].get("name") or f"Addon {addon_id}"
        super().__init__(coordinator, f"timed_{addon_id}", translation_key="wiked_timed",
                         placeholders={"output": name})

    @property
    def duration(self):
        return self.coordinator.duration_for(self.addon_id)

    @property
    def available(self):
        return super().available and "relay" in (self.coordinator.data or {}).get(self.addon_id, {})

    async def async_press(self):
        await self.coordinator.command(self.addon_id, True, self.duration)


def entities_for(coordinator, platform):
    """Create only entities backed by actual advertised features."""
    entities = []
    for i, info in coordinator.addons.items():
        kind = info["type"]
        state = (coordinator.data or {}).get(i, {})
        if platform == "light" and kind == "switch" and "relay" in state:
            entities.append(WikedLight(coordinator, i))
        elif platform == "switch" and kind == "settingsSwitch" and state.get("settingsSwitch", {}).get("path") == "settings/gate/conditionalAction/execute":
            entities.append(WikedSettingsSwitch(coordinator, i))
        elif platform == "binary_sensor" and kind == "sensor" and state.get("sensor", {}).get("type") == "lock":
            entities.append(WikedBolt(coordinator, i))
        elif platform == "button" and kind == "switch" and "relay" in state:
            entities.append(WikedTimedLight(coordinator, i))
        elif platform == "number" and kind == "switch" and "relay" in state:
            entities.append(WikedDuration(coordinator, i))
    if platform == "binary_sensor":
        entities.append(WikedS1(coordinator))
    if platform == "button":
        covers = coordinator.native.box.features.get("covers", [])
        if len(covers) == 1:
            entities.append(WikedRelease(coordinator, covers[0]))
    return entities

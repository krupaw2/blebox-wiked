"""Local WIKED input events and explicit device-side action provisioning."""
from ipaddress import ip_address
import logging
import secrets
from urllib.parse import urlsplit

from aiohttp import ClientError, ClientTimeout
from blebox_uniapi.error import Error
from homeassistant.components import webhook
from homeassistant.components.button import ButtonEntity
from homeassistant.components.event import EventEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.network import get_url
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .wiked import WikedEntity, bit, state_map

_LOGGER = logging.getLogger(__name__)
INPUTS = (0, 1)
NAMES = {0: "HA IN1", 1: "HA IN2"}
PATH = "/api/webhook/"
HANDLE_PATH = "settings/gate/conditionalAction/execute"
FIELDS = ("id", "name", "input", "triggerType", "actionType", "param",
          "intervalS", "triggerParam")


def action_fields(action):
    """Exclude changing runtime metadata when comparing configuration."""
    return tuple(action.get(k) for k in FIELDS)


def make_action(slot, channel, url):
    """Use the request envelope observed in wBox traffic."""
    return {"id": slot, "name": NAMES[channel], "input": channel,
            "triggerType": 4, "actionType": 50,
            "lastCall": {"timeElapsedS": -1}, "triggerParam": 0,
            "param": url, "throttleS": 0, "intervalS": 0}


def action_map(response):
    """Validate device action inventory before attempting any write."""
    if not isinstance(response, dict) or not isinstance(response.get("actions"), list):
        raise ValueError("Invalid action inventory")
    limit = response.get("itemsLimit")
    if type(limit) is not int or not 1 <= limit <= 256:
        raise ValueError("Invalid action capacity")
    actions = {}
    for item in response["actions"]:
        if not isinstance(item, dict):
            raise ValueError("Invalid action")
        i = item.get("id")
        if type(i) is not int or not 0 <= i < limit or i in actions:
            raise ValueError("Invalid or duplicate action ID")
        actions[i] = item
    if len(actions) != limit:
        raise ValueError("Incomplete action inventory")
    return actions


def plan_actions(actions, urls, tokens):
    """Reuse only actions owned by this entry; never replace user actions."""
    result = []
    remaining = set(actions)
    for channel in INPUTS:
        owned = [i for i in remaining
                 if actions[i].get("name") == NAMES[channel]
                 and actions[i].get("actionType") == 50
                 and actions[i].get("input") == channel
                 and isinstance(actions[i].get("param"), str)
                 and urlsplit(actions[i]["param"]).path == PATH + tokens[str(channel)]]
        if len(owned) > 1:
            raise ValueError("Duplicate managed action")
        if owned:
            slot = owned[0]
        else:
            empty = [i for i in remaining if
                     actions[i].get("name") == ""
                     and actions[i].get("param") == ""
                     and actions[i].get("triggerType") == 0
                     and actions[i].get("actionType") == 0]
            if not empty:
                raise ValueError("No free action slot")
            slot = min(empty)
        remaining.remove(slot)
        desired = make_action(slot, channel, urls[channel])
        if action_fields(actions[slot]) != action_fields(desired):
            result.append(desired)
    return result


def event_type(channel, enabled):
    if channel == 0 or enabled is False:
        return "doorbell"
    if enabled is True:
        return "pressed"
    return "pressed_unknown"


def local_base(hass):
    """Prefer the directly reachable local HA API; never use a cloud URL."""
    api = hass.config.api
    if api is not None and not api.use_ssl:
        try:
            ip = ip_address(api.local_ip)
            if ip.version == 4 and ip.is_private and not ip.is_loopback and not ip.is_unspecified:
                return f"http://{ip}:{api.port}"
        except (ValueError, TypeError):
            pass
    url = get_url(hass, allow_external=False, allow_cloud=False, prefer_external=False)
    parsed = urlsplit(url)
    if parsed.scheme != "http" or not parsed.hostname or parsed.path not in ("", "/"):
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key="wiked_local_http")
    try:
        ip = ip_address(parsed.hostname)
    except ValueError:
        if not parsed.hostname.endswith(".local"):
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="wiked_local_host") from None
    else:
        if not ip.is_private or ip.is_loopback or ip.is_unspecified:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="wiked_local_address")
    return url.rstrip("/")


class InputEvents:
    def __init__(self, hass, coordinator, session, tokens):
        self.hass = hass
        self.coordinator = coordinator
        self.session = session
        self.tokens = tokens
        self.entities = {}

    async def configure(self):
        """Explicit opt-in: provision only separately allocated URL actions."""
        coordinator = self.coordinator
        urls = {i: local_base(self.hass) + PATH + self.tokens[str(i)] for i in INPUTS}
        try:
            async with coordinator.io_lock:
                api = coordinator.api_host
                before = action_map(await api.async_api_get("/api/actions/state"))
                changes = plan_actions(before, urls, self.tokens)
                for desired in changes:
                    # Re-read immediately before each write to reduce races with wBox.
                    current = action_map(await api.async_api_get("/api/actions/state"))
                    if {i: action_fields(a) for i, a in current.items()} != {
                        i: action_fields(a) for i, a in before.items()
                    }:
                        raise ValueError("Action configuration changed concurrently")
                    slot = desired["id"]
                    async with self.session.post(
                        api.api_path("/api/actions/set"), json={"action": desired},
                        timeout=ClientTimeout(total=10), allow_redirects=False,
                    ) as response:
                        if response.status != 200:
                            raise ValueError(f"Action write failed: HTTP {response.status}")
                    after = action_map(await api.async_api_get("/api/actions/state"))
                    expected = dict(before)
                    expected[slot] = desired
                    if {i: action_fields(a) for i, a in after.items()} != {
                        i: action_fields(a) for i, a in expected.items()
                    }:
                        raise ValueError("Action read-back did not match; further writes stopped")
                    before = after
        except (Error, ClientError, OSError, TimeoutError, ValueError):
            # Do not expose webhook secrets in HA errors or logs.
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="wiked_action_failed") from None

    async def handle(self, channel):
        """A callback never issues a release command."""
        enabled = None
        if channel == 1:
            try:
                async with self.coordinator.io_lock:
                    data = state_map(await self.coordinator.api_host.async_api_get("/state"))
                    for value in data.values():
                        if isinstance(value, dict) and value.get("settingsSwitch", {}).get("path") == HANDLE_PATH:
                            enabled = bit(value, "settingsSwitch", "value")
                            break
            except (Error, OSError, TimeoutError, ValueError):
                _LOGGER.debug("Could not read WIKED handle setting for input event")
        if entity := self.entities.get(channel):
            entity.emit(event_type(channel, enabled), enabled)


async def async_prepare_inputs(hass, entry, coordinator, session):
    """Register local secret endpoints; do not write to the controller on startup."""
    try:
        response = await coordinator.api_host.async_api_get("/api/actions/state")
        action_map(response)
        store = Store(hass, 1, f"blebox_wiked_inputs.{entry.entry_id}", private=True)
        tokens = await store.async_load()
        if tokens is None:
            tokens = {str(i): secrets.token_hex(16) for i in INPUTS}
            await store.async_save(tokens)
        if not isinstance(tokens, dict) or not all(
            isinstance(tokens.get(str(i)), str) and len(tokens[str(i)]) == 32
            for i in INPUTS
        ) or len(set(tokens.values())) != 2:
            raise ValueError("Invalid stored webhook identifiers")
        manager = InputEvents(hass, coordinator, session, tokens)
        registered = []
        try:
            for i in INPUTS:
                async def receive(hass, webhook_id, request, channel=i):
                    await manager.handle(channel)
                token = tokens[str(i)]
                webhook.async_register(hass, DOMAIN, f"WIKED IN{i+1}",
                                       token, receive, local_only=True,
                                       allowed_methods=("GET",))
                registered.append(token)
        except Exception:
            for token in registered:
                webhook.async_unregister(hass, token)
            raise
        for token in registered:
            entry.async_on_unload(lambda token=token: webhook.async_unregister(hass, token))
        coordinator.input_events = manager
    except (Error, ClientError, OSError, TimeoutError, ValueError, HomeAssistantError):
        _LOGGER.warning("WIKED input events unavailable; existing door controls retained")


class WikedInputEvent(WikedEntity, EventEntity):
    _attr_event_types = ["doorbell", "pressed", "pressed_unknown"]

    def __init__(self, coordinator, channel):
        self.channel = channel
        self.manager = coordinator.input_events
        super().__init__(coordinator, f"input_{channel}", translation_key="wiked_input",
                         placeholders={"input": f"IN{channel+1}"})
        self._attr_icon = "mdi:bell-ring-outline" if channel == 0 else "mdi:gesture-tap-button"

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.manager.entities[self.channel] = self
        self.async_on_remove(lambda: self.manager.entities.pop(self.channel, None))

    def emit(self, kind, enabled):
        self._trigger_event(kind, {"input": self.channel + 1, "handle_enabled": enabled})
        self.async_write_ha_state()


class WikedConfigureInputs(WikedEntity, ButtonEntity):
    _attr_icon = "mdi:webhook"

    def __init__(self, coordinator):
        super().__init__(coordinator, "configure_inputs", translation_key="wiked_configure_inputs")

    async def async_press(self):
        await self.coordinator.input_events.configure()


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = getattr(config_entry.runtime_data, "wiked", None)
    if coordinator is not None and getattr(coordinator, "input_events", None) is not None:
        async_add_entities([WikedInputEvent(coordinator, i) for i in INPUTS])

"""Radiooooo: play music from any decade and country on any media player."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import RadiooooAuthError, RadiooooClient, RadiooooError
from .const import CONF_EMAIL, CONF_PASSWORD, DECADES, DOMAIN, MODES, MOODS, SERVICE_PLAY
from .controller import RadiooooController

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.SELECT]

PLAY_SCHEMA = vol.Schema(
    {
        vol.Optional("mode"): vol.In(MODES),
        vol.Optional("moods"): vol.All(cv.ensure_list, [vol.All(vol.Upper, vol.In(MOODS))]),
        vol.Optional("countries"): vol.All(cv.ensure_list, [vol.All(cv.string, vol.Upper)]),
        vol.Optional("decades"): vol.All(cv.ensure_list, [vol.All(vol.Coerce(int), vol.In(DECADES))]),
        vol.Optional("island"): cv.string,
        vol.Optional("target"): cv.entity_id,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Own session: the API relies on a connect.sid cookie that must not leak into HA's shared jar.
    session = async_create_clientsession(hass)
    client = RadiooooClient(session)

    try:
        if entry.data.get(CONF_EMAIL):
            await client.login(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
        islands = await client.islands()
        countries = await client.countries()
    except RadiooooAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except RadiooooError as err:
        raise ConfigEntryNotReady(str(err)) from err

    controller = RadiooooController(hass, client, entry.entry_id)
    controller.island_map = {i["name"]: i["_id"] for i in islands}
    controller.country_codes = countries
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def handle_play(call: ServiceCall) -> None:
        ctrl: RadiooooController = next(iter(hass.data[DOMAIN].values()))
        data = dict(call.data)
        if "island" in data:
            # Accept either an island name or its id.
            data["island"] = ctrl.island_map.get(data["island"], data["island"])
        ctrl.set_context(
            mode=data.get("mode"),
            moods=data.get("moods"),
            countries=data.get("countries"),
            decades=data.get("decades"),
            island=data.get("island"),
            output=data.get("target"),
        )
        try:
            await ctrl.async_play()
        except RadiooooError as err:
            raise ServiceValidationError(str(err)) from err

    if not hass.services.has_service(DOMAIN, SERVICE_PLAY):
        hass.services.async_register(DOMAIN, SERVICE_PLAY, handle_play, schema=PLAY_SCHEMA)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    hass.data[DOMAIN].pop(entry.entry_id).shutdown()
    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, SERVICE_PLAY)
    return True

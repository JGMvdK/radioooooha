"""Radiooooo: play music from any decade and country on any media player."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import RadiooooAuthError, RadiooooClient, RadiooooError
from .const import CONF_EMAIL, CONF_PASSWORD, DECADES, DOMAIN, MODES, MOODS, SERVICE_PLAY
from .controller import RadiooooController

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.SELECT]

CATEGORY_ORDER = ["thematic", "artists", "flux", "podcast", "top10", ""]
CATEGORY_NAMES = {"thematic": "Thematic", "artists": "Artist", "flux": "Top 100", "podcast": "Podcast", "top10": "Top 10"}


def island_labels(islands: list[dict]) -> dict[str, str]:
    """Readable, unique, grouped labels -> island id. Top 10 islands are only named "#29", so add the date."""

    def sort_key(i: dict) -> tuple:
        cat = i.get("category") or ""
        rank = CATEGORY_ORDER.index(cat) if cat in CATEGORY_ORDER else len(CATEGORY_ORDER)
        # Newest weekly Top 10 first; everything else alphabetical.
        num = int(i["name"].lstrip("#")) if cat == "top10" and i["name"].lstrip("#").isdigit() else 0
        return (rank, -num, i["name"].lower())

    labels: dict[str, str] = {}
    for i in sorted(islands, key=sort_key):
        cat = i.get("category") or ""
        name = i["name"] if cat != "top10" else f"{i['name']} ({i['info']})" if i.get("info") else i["name"]
        label = f"{CATEGORY_NAMES.get(cat, 'Other')}: {name}"
        labels.setdefault(label, i["_id"])
    return labels


def resolve_island(labels: dict[str, str], value: str) -> str:
    """Accept a full label, a bare island name, or a raw id."""
    if value in labels:
        return labels[value]
    wanted = value.lower()
    return next((i for label, i in labels.items() if label.split(": ", 1)[-1].lower() == wanted), value)


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
    controller.island_map = island_labels(islands)
    controller.country_codes = countries
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller

    # The output player used to be a select; it's now the media player's source.
    registry = er.async_get(hass)
    if old := registry.async_get_entity_id("select", DOMAIN, f"{entry.entry_id}_output"):
        registry.async_remove(old)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def handle_play(call: ServiceCall) -> None:
        ctrl: RadiooooController = next(iter(hass.data[DOMAIN].values()))
        data = dict(call.data)
        if "island" in data:
            # Accept either an island name or its id.
            data["island"] = resolve_island(ctrl.island_map, data["island"])
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

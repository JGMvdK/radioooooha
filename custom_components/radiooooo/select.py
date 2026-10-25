"""Select entities that edit the playback context (applies from the next track)."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DECADES, DOMAIN, MODE_EXPLORE, MODE_ISLAND, MODE_RANDOM
from .controller import RadiooooController
from .entity import RadiooooEntity

ANY = "Any"
NONE = "None"

MODE_LABELS = {MODE_RANDOM: "Random", MODE_EXPLORE: "Explore", MODE_ISLAND: "Island"}
MOOD_LABELS = {
    "Slow": ["SLOW"],
    "Fast": ["FAST"],
    "Weird": ["WEIRD"],
    "Slow + Fast": ["SLOW", "FAST"],
    "All": ["SLOW", "FAST", "WEIRD"],
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    c: RadiooooController = hass.data[DOMAIN][entry.entry_id]
    id_ = entry.entry_id
    async_add_entities(
        [
            RadiooooSelect(
                c, id_, "mode", "Mode",
                options=lambda: list(MODE_LABELS.values()),
                current=lambda: MODE_LABELS[c.mode],
                select=lambda v: c.set_context(mode=_key(MODE_LABELS, v)),
            ),
            RadiooooSelect(
                c, id_, "mood", "Mood",
                options=lambda: list(MOOD_LABELS),
                current=lambda: next((k for k, v in MOOD_LABELS.items() if v == c.moods), None),
                select=lambda v: c.set_context(moods=MOOD_LABELS[v]),
            ),
            RadiooooSelect(
                c, id_, "decade", "Decade",
                options=lambda: [ANY, *map(str, DECADES)],
                current=lambda: ANY if not c.decades else (str(c.decades[0]) if len(c.decades) == 1 else None),
                select=lambda v: c.set_context(decades=[] if v == ANY else [int(v)]),
            ),
            RadiooooSelect(
                c, id_, "country", "Country",
                options=lambda: [ANY, *c.country_codes],
                current=lambda: ANY if not c.countries else (c.countries[0] if len(c.countries) == 1 else None),
                select=lambda v: c.set_context(countries=[] if v == ANY else [v]),
            ),
            RadiooooSelect(
                c, id_, "island", "Island",
                options=lambda: [NONE, *sorted(c.island_map)],
                current=lambda: next((n for n, i in c.island_map.items() if i == c.island), NONE),
                select=lambda v: c.set_context(island=c.island_map.get(v, "")),
            ),
            RadiooooSelect(
                c, id_, "output", "Output player",
                # Evaluated on each state write, so players added later show up after the next change.
                options=lambda: [
                    NONE,
                    *sorted(
                        e for e in hass.states.async_entity_ids("media_player") if e != player_id(hass, id_)
                    ),
                ],
                current=lambda: c.output or NONE,
                select=lambda v: c.set_context(output="" if v == NONE else v),
            ),
        ]
    )


def player_id(hass: HomeAssistant, entry_id: str) -> str | None:
    """Entity id of our own media player, so it can't be picked as its own output."""
    return er.async_get(hass).async_get_entity_id("media_player", DOMAIN, f"{entry_id}_player")


def _key(labels: dict[str, str], value: str) -> str:
    return next(k for k, v in labels.items() if v == value)


class RadiooooSelect(RadiooooEntity, SelectEntity):
    def __init__(
        self,
        controller: RadiooooController,
        entry_id: str,
        key: str,
        name: str,
        *,
        options: Callable[[], list[str]],
        current: Callable[[], str | None],
        select: Callable[[str], None],
    ) -> None:
        super().__init__(controller, entry_id, key)
        self._attr_name = name
        self._options, self._current, self._select = options, current, select

    @property
    def options(self) -> list[str]:
        return self._options()

    @property
    def current_option(self) -> str | None:
        return self._current()

    async def async_select_option(self, option: str) -> None:
        self._select(option)

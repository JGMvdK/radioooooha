"""Media player entity: shows the current track and offers play / stop / next."""

from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import RadiooooError, cover_url
from .const import DOMAIN
from .entity import RadiooooEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([RadiooooPlayer(hass.data[DOMAIN][entry.entry_id], entry.entry_id)])


class RadiooooPlayer(RadiooooEntity, MediaPlayerEntity):
    _attr_name = None
    _attr_media_content_type = MediaType.MUSIC
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.SEEK
    )

    def __init__(self, controller, entry_id: str) -> None:
        super().__init__(controller, entry_id, "player")

    @property
    def _output_state(self):
        return self.hass.states.get(self.controller.output) if self.controller.output else None

    @property
    def state(self) -> MediaPlayerState:
        if not self.controller.playing:
            return MediaPlayerState.IDLE
        out = self._output_state
        return MediaPlayerState.PAUSED if out and out.state == "paused" else MediaPlayerState.PLAYING

    @property
    def source_list(self) -> list[str]:
        """Every other media player; the chosen one plays the audio."""
        return sorted(
            e for e in self.hass.states.async_entity_ids("media_player") if e != self.entity_id
        )

    @property
    def source(self) -> str | None:
        return self.controller.output or None

    @property
    def volume_level(self) -> float | None:
        out = self._output_state
        return out.attributes.get("volume_level") if out else None

    async def async_select_source(self, source: str) -> None:
        old_output = self.controller.output
        self.controller.set_context(output=source)
        await self._run(self.controller.async_apply_change(old_output))

    async def async_set_volume_level(self, volume: float) -> None:
        if self.controller.output:
            await self._forward("volume_set", volume_level=volume)

    async def async_media_seek(self, position: float) -> None:
        await self.controller.async_seek(position)

    async def async_media_pause(self) -> None:
        await self._forward("media_pause")

    async def _forward(self, service: str, **data) -> None:
        await self.hass.services.async_call(
            "media_player", service, {"entity_id": self.controller.output, **data}, blocking=False
        )

    @property
    def _track(self) -> dict:
        return self.controller.track or {}

    @property
    def media_title(self) -> str | None:
        return self._track.get("title")

    @property
    def media_artist(self) -> str | None:
        return self._track.get("artist")

    @property
    def media_album_name(self) -> str | None:
        return self._track.get("album")

    @property
    def media_position(self) -> int | None:
        if not self.controller.playing:
            return None
        out = self._output_state
        if out and out.attributes.get("media_position") is not None:
            return out.attributes["media_position"]  # the speaker knows best (pause, seek, buffering)
        return int((dt_util.utcnow() - self.controller.track_started_at).total_seconds())

    @property
    def media_position_updated_at(self):
        if not self.controller.playing:
            return None
        out = self._output_state
        if out and out.attributes.get("media_position_updated_at") is not None:
            return out.attributes["media_position_updated_at"]
        return self.controller.track_started_at

    @property
    def media_duration(self) -> int | None:
        return self._track.get("length")

    @property
    def media_image_url(self) -> str | None:
        return cover_url(self._track) if self._track else None

    @property
    def media_image_remotely_accessible(self) -> bool:
        return True

    @property
    def extra_state_attributes(self) -> dict:
        t = self._track
        return {
            "country": t.get("country"),
            "decade": t.get("decade"),
            "mood": t.get("mood"),
            "year": t.get("year"),
            "label": t.get("label"),
            "likes": t.get("likes"),
            "output": self.controller.output,
            "mode": self.controller.mode,
            "error": self.controller.error,
            "settings_entities": self._settings_entities(),
        }

    def _settings_entities(self) -> dict[str, str | None]:
        """Select entity ids the radiooooo-card edits (their ids are user-renamable, so look them up)."""
        registry = er.async_get(self.hass)
        entry_id = self.registry_entry.config_entry_id if self.registry_entry else None
        return {
            key: registry.async_get_entity_id("select", DOMAIN, f"{entry_id}_{key}")
            for key in ("mode", "mood", "country", "decade", "island")
        }

    async def _run(self, coro) -> None:
        try:
            await coro
        except RadiooooError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_media_play(self) -> None:
        out = self._output_state
        if self.controller.playing and out and out.state == "paused":
            await self._forward("media_play")  # resume rather than skipping to a new track
        else:
            await self._run(self.controller.async_play())

    async def async_media_next_track(self) -> None:
        await self._run(self.controller.async_play())

    async def async_media_stop(self) -> None:
        await self.controller.async_stop()

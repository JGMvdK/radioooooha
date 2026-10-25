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
    )

    def __init__(self, controller, entry_id: str) -> None:
        super().__init__(controller, entry_id, "player")

    @property
    def state(self) -> MediaPlayerState:
        return MediaPlayerState.PLAYING if self.controller.playing else MediaPlayerState.IDLE

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
        }

    async def _run(self, coro) -> None:
        try:
            await coro
        except RadiooooError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_media_play(self) -> None:
        await self._run(self.controller.async_play())

    async def async_media_next_track(self) -> None:
        await self._run(self.controller.async_play())

    async def async_media_stop(self) -> None:
        await self.controller.async_stop()

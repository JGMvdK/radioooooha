"""Holds the playback context and drives an output media_player track by track."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from .api import RadiooooClient, RadiooooError, cover_url, stream_url
from .const import (
    DEFAULT_TRACK_SECONDS,
    END_SLACK_SECONDS,
    END_TOLERANCE_SECONDS,
    MODE_RANDOM,
    MOODS,
    SWITCH_GRACE_SECONDS,
)

_LOGGER = logging.getLogger(__name__)

STOPPED_STATES = {"idle", "off", "standby", "unavailable"}


class RadiooooController:
    """Context (mode/moods/countries/decades/island/output) plus the play loop.

    Changing the context affects the *next* track; the current one finishes.
    """

    def __init__(self, hass: HomeAssistant, client: RadiooooClient, entry_id: str) -> None:
        self.hass = hass
        self.client = client
        self.signal = f"radiooooo_update_{entry_id}"

        self.mode = MODE_RANDOM
        self.moods: list[str] = ["SLOW", "FAST"]
        self.countries: list[str] = []
        self.decades: list[int] = []
        self.island: str | None = None
        self.output: str | None = None

        self.island_map: dict[str, str] = {}  # island name -> id, filled at setup
        self.country_codes: list[str] = []

        self.track: dict | None = None
        self.playing = False
        self.error: str | None = None

        self._generation = 0  # bumps on every play/stop so stale callbacks self-cancel
        self._started_at = 0.0
        self._unsub_state: CALLBACK_TYPE | None = None
        self._unsub_timer: CALLBACK_TYPE | None = None

    @callback
    def changed(self) -> None:
        async_dispatcher_send(self.hass, self.signal)

    @callback
    def set_context(
        self,
        *,
        mode: str | None = None,
        moods: list[str] | None = None,
        countries: list[str] | None = None,
        decades: list[int] | None = None,
        island: str | None = None,
        output: str | None = None,
    ) -> None:
        if mode is not None:
            self.mode = mode
        if moods is not None:
            self.moods = [m for m in MOODS if m in moods]
        if countries is not None:
            self.countries = countries
        if decades is not None:
            self.decades = decades
        if island is not None:
            self.island = island
        if output is not None:
            self.output = output
        self.changed()

    async def async_play(self) -> None:
        """Fetch a track for the current context and send it to the output player."""
        if not self.output:
            raise RadiooooError("no output player selected")
        self._cancel_watchers()
        self._generation += 1
        generation = self._generation

        try:
            track = await self.client.next_track(
                self.mode, self.moods, self.countries, self.decades, self.island
            )
        except RadiooooError as err:
            self.error = str(err)
            self.playing = False
            self.changed()
            raise
        if generation != self._generation:
            return  # superseded while fetching

        self.error = None
        self.track = track
        self.playing = True
        self._started_at = time.monotonic()
        length = int(track.get("length") or DEFAULT_TRACK_SECONDS)

        self._unsub_state = async_track_state_change_event(
            self.hass, [self.output], lambda event: self._output_changed(event, generation, length)
        )
        self._unsub_timer = async_call_later(
            self.hass, length + END_SLACK_SECONDS, lambda _now: self._advance(generation)
        )
        await self._send_to_output(track)
        self.changed()

    async def async_stop(self) -> None:
        self._cancel_watchers()
        self._generation += 1
        was_playing, self.playing = self.playing, False
        self.changed()
        if was_playing and self.output:
            await self.hass.services.async_call(
                "media_player", "media_stop", {"entity_id": self.output}, blocking=False
            )

    def shutdown(self) -> None:
        self._cancel_watchers()
        self._generation += 1
        self.playing = False

    async def _send_to_output(self, track: dict) -> None:
        extra: dict = {
            "title": track.get("title"),
            "metadata": {"metadataType": 3, "title": track.get("title"), "artist": track.get("artist")},
        }
        if thumb := cover_url(track):
            extra["thumb"] = thumb
        await self.hass.services.async_call(
            "media_player",
            "play_media",
            {
                "entity_id": self.output,
                "media_content_id": stream_url(track),
                "media_content_type": "music",
                "extra": extra,
            },
            blocking=False,
        )

    @callback
    def _output_changed(self, event: Event, generation: int, length: int) -> None:
        if generation != self._generation:
            return
        new = event.data.get("new_state")
        if new is None or new.state not in STOPPED_STATES:
            return
        elapsed = time.monotonic() - self._started_at
        if elapsed < SWITCH_GRACE_SECONDS:
            return
        if elapsed >= length - END_TOLERANCE_SECONDS:
            self._advance(generation)
        else:
            _LOGGER.debug("Output stopped after %.0fs of %ds; treating as user stop", elapsed, length)
            self.hass.async_create_task(self._user_stopped(generation))

    @callback
    def _advance(self, generation: int) -> None:
        if generation != self._generation:
            return
        self.hass.async_create_task(self._play_next_logged())

    async def _play_next_logged(self) -> None:
        try:
            await self.async_play()
        except RadiooooError as err:
            _LOGGER.error("Could not fetch next track: %s", err)

    async def _user_stopped(self, generation: int) -> None:
        if generation != self._generation:
            return
        self._cancel_watchers()
        self._generation += 1
        self.playing = False
        self.changed()

    def _cancel_watchers(self) -> None:
        for unsub in (self._unsub_state, self._unsub_timer):
            if unsub:
                unsub()
        self._unsub_state = self._unsub_timer = None

"""Client for the unofficial Radiooooo web API (reverse engineered from app.radiooooo.com)."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import ASSET_URL, BASE_URL, GEODATA_URL, MODE_EXPLORE, MODE_ISLAND, MODE_RANDOM, RANDOM_MOODS

_LOGGER = logging.getLogger(__name__)

# Cloudflare fronts the API; a browser-like UA avoids needless challenges.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36 HomeAssistant",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/",
}


class RadiooooError(Exception):
    """API call failed."""


class RadiooooAuthError(RadiooooError):
    """Login rejected."""


class RadiooooClient:
    """Thin wrapper over the JSON endpoints. Session must have its own cookie jar."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        url = f"{BASE_URL}{path}"
        try:
            async with self._session.request(
                method, url, json=body, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    raise RadiooooError(f"{method} {path} -> {resp.status}: {data}")
                return data
        except (aiohttp.ClientError, TimeoutError) as err:
            raise RadiooooError(f"{method} {path} failed: {err}") from err

    async def login(self, email: str, password: str) -> None:
        try:
            data = await self._request("POST", "/account/login", {"email": email, "password": password})
        except RadiooooError as err:
            raise RadiooooAuthError(str(err)) from err
        if isinstance(data, dict) and data.get("error"):
            raise RadiooooAuthError(str(data["error"]))

    async def islands(self) -> list[dict]:
        data = await self._request("GET", "/island/list")
        return [i for i in data if i.get("enabled")]

    async def countries(self) -> list[str]:
        """ISO-3 codes of every country on the map."""
        async with self._session.get(GEODATA_URL, headers=HEADERS) as resp:
            geo = await resp.json(content_type=None)
        return sorted(f["properties"]["id"] for f in geo["features"] if f.get("properties", {}).get("id"))

    async def next_track(
        self,
        mode: str,
        moods: list[str],
        countries: list[str],
        decades: list[int],
        island: str | None,
    ) -> dict:
        """Fetch one track for the given context. Empty country/decade lists mean "any"."""
        if mode == MODE_RANDOM:
            body = {
                "mode": "random",
                "moods": [m for m in moods if m in RANDOM_MOODS] or RANDOM_MOODS,
                "priority": "auto",
            }
            track = await self._request("POST", "/play/random", body)
        elif mode == MODE_ISLAND:
            if not island:
                raise RadiooooError("island mode needs an island")
            body = {"mode": "islands", "island": island, "moods": moods}
            track = await self._request("POST", "/play", body)
        else:
            body = {"mode": MODE_EXPLORE, "isocodes": countries, "decades": decades, "moods": moods}
            track = await self._request("POST", "/play", body)

        if not isinstance(track, dict) or not track.get("links"):
            raise RadiooooError(f"no track returned for {body}: {track}")
        return track


def stream_url(track: dict) -> str:
    return track["links"].get("mpeg") or track["links"]["ogg"]


def cover_url(track: dict) -> str | None:
    cover = track.get("cover") or track.get("image")
    if not cover:
        return None
    return f"{ASSET_URL}/{cover['path']}300x300/{cover['filename']}"

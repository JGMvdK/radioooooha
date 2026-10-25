# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Home Assistant custom integration (`custom_components/radiooooo`, HACS-installable) for Radiooooo. It uses the site's **undocumented, reverse-engineered web API** (`https://app.radiooooo.com`), so endpoints may change without notice. There is no build step, linter config or test suite.

## Working without Home Assistant installed

HA isn't available locally, so verification is limited:
- Syntax check: `python -m py_compile custom_components/radiooooo/*.py`, then delete the generated `__pycache__` dirs.
- `api.py` depends only on `aiohttp` and can be smoke-tested against the live API in a venv (load modules via `importlib` under a fake package, since `__init__.py` imports `homeassistant`).
- Everything else (entities, controller, services) only runs inside HA. To test: copy `custom_components/radiooooo` to the HA `config/custom_components/`, **restart** HA (reload doesn't pick up code changes), and check logs. `logs/` holds HA log dumps; the integration logs each API request at info level (`Requested <mode> {...} -> got <country>/<decade> <title>`) when `logger: logs: custom_components.radiooooo: info` is set.

## Architecture

`RadiooooController` ([controller.py](custom_components/radiooooo/controller.py)) is the core; one instance per config entry, stored in `hass.data[DOMAIN][entry_id]`. It holds the playback context (mode, moods, countries, decades, island, output player) and the current track, and drives the play loop. Entities don't hold state; they read from the controller and refresh via a dispatcher signal (`controller.changed()` → `RadiooooEntity._handle_update`).

Playback flow: `async_play()` asks `RadiooooClient.next_track()` for one track, then calls `media_player.play_media` on the chosen **output player** (any other HA media_player) with the signed MP3 URL. The integration is a remote control; it never plays audio itself. The next track is triggered by: the output player going idle near the track end (`_output_changed`), or a fallback timer at `length + END_SLACK_SECONDS`. A `_generation` counter invalidates stale callbacks after every play/stop. Idle early in a track counts as a user stop; the first `SWITCH_GRACE_SECONDS` are ignored because players go idle while switching media.

Entry points into the controller, all of which should go through `set_context` / `async_apply_change`:
- `select.py`: mode/mood/decade/country/island selects. Picking a country or decade switches mode to Explore and clears the island; picking an island switches to Island and clears country/decade. Changes made while playing fetch a new track immediately.
- `media_player.py`: the output player is the media player's **source**; play/pause/seek/volume are forwarded to it (`controller.async_seek` also re-arms the fallback timer). Position/duration come from the output player when it reports them.
- `www/radiooooo-card.js`: vanilla-JS Lovelace card (no build step) served by `_register_card` in `__init__.py` and auto-loaded via `add_extra_js_url`. It finds the select entities through the media player's `settings_entities` attribute, so keep that attribute in sync with the select keys. Syntax check: `node --check`.
- `radiooooo.play` service (registered in `__init__.py`, schema + `resolve_island`).

### API quirks (see `api.py`)
- Three request shapes: `POST /play/random` (random; only SLOW/FAST moods, WEIRD is rejected), `POST /play` with `mode: explore` (empty `isocodes`/`decades` = any) and `mode: islands` (needs `island` id).
- Track audio URLs are signed and expire, so never cache them; fetch right before playing.
- Auth is optional (`POST /account/login`); the session cookie `connect.sid` lives in a dedicated aiohttp session (`async_create_clientsession`) so it doesn't touch HA's shared jar.
- Islands come from `GET /island/list` (391 entries); `island_labels()` in `__init__.py` groups them by category and builds the select labels. Top 10 islands are only named `#29` etc., so the date from `info` is appended.
- Country list is derived from the map GeoJSON (ISO-3 ids only, no names).

## Gotchas
- Callbacks passed to HA helpers (`async_track_state_change_event`, `async_call_later`) must be wrapped with `@callback`/`callback(...)`; otherwise HA runs them in a worker thread and `hass.async_create_task` fails.
- `strings.json` and `translations/en.json` must be kept identical (copy after editing).
- Bump `version` in `manifest.json` and cut a matching GitHub release for HACS to offer updates.

# Radiooooo for Home Assistant

Unofficial custom integration. Plays [Radiooooo](https://radiooooo.com) (music from any decade and country) on any Home Assistant `media_player` (Cast, Sonos, ...). It uses the site's undocumented web API, which may change without notice.

## Install
Copy `custom_components/radiooooo` into your HA `config/custom_components/` (or add this repo to HACS as a custom repository), restart, then **Settings → Devices & services → Add integration → Radiooooo**. Email/password are optional; leave blank to use it anonymously.

## Entities
- `media_player.radiooooo` — current track (title, artist, cover, country/decade/mood attributes). Play, pause, stop, next and volume are forwarded to the output player; choose that player with the card's **source** menu (every other `media_player`).
- `select.radiooooo_*` — mode, mood, decade, country (ISO-3) and island (grouped by category, e.g. `Thematic: Kids Playground`, `Top 10: #29 (07/05/21)`). Changing one while playing switches to a new track immediately.

## Card
The integration ships a Lovelace card and loads it automatically (hard-refresh the browser once after updating). Add it to a dashboard:
```yaml
type: custom:radiooooo-card
entity: media_player.radiooooo
```
Buttons: cast (pick the output player), stop, play/pause, next. Clicking anywhere else on the card opens a settings modal with mode, mood, country, decade, island and output player. Home Assistant's own media dialog can't host those settings, hence the custom card.

## How mode, country, decade and island interact
Mode decides what is used: **Random** uses only mood; **Explore** uses country + decade (+ mood); **Island** uses the island (+ mood). Picking a country or decade switches to Explore and clears the island; picking an island switches to Island and clears country/decade.

## Service `radiooooo.play`
```yaml
service: radiooooo.play
data:
  mode: explore
  moods: [SLOW, FAST]
  countries: [FRA, ITA]
  decades: [1960, 1970]
  target: media_player.kitchen
```
Omitted fields keep their current value; empty `countries`/`decades` mean any. Random mode ignores `WEIRD`; island mode needs `island` (name or id).

## Notes
- Audio URLs are signed and expire, so the next track is fetched when the previous one ends (detected from the output player going idle, with a timer fallback).
- Output players must be able to reach `radiooooo-track.b-cdn.net`.
- Google/Facebook/Apple sign-in isn't supported; use email + password.

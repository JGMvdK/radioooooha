# Radiooooo for Home Assistant

Unofficial custom integration. Plays [Radiooooo](https://radiooooo.com) (music from any decade and country) on any Home Assistant `media_player` (Cast, Sonos, ...). It uses the site's undocumented web API, which may change without notice.

## Install
Copy `custom_components/radiooooo` into your HA `config/custom_components/` (or add this repo to HACS as a custom repository), restart, then **Settings → Devices & services → Add integration → Radiooooo**. Email/password are optional; leave blank to use it anonymously.

## Entities
- `media_player.radiooooo` — current track (title, artist, cover, country/decade/mood attributes); play / stop / next.
- `select.radiooooo_*` — mode (random/explore/island), mood, decade, country (ISO-3), island, output player. Changes apply from the next track.

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

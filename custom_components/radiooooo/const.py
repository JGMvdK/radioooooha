"""Constants for the Radiooooo integration."""

from datetime import timedelta

DOMAIN = "radiooooo"

BASE_URL = "https://app.radiooooo.com"
ASSET_URL = "https://asset.radiooooo.com"
GEODATA_URL = "https://static.radiooooo.com/beta/geodata/base.geojson"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"

MODE_RANDOM = "random"
MODE_EXPLORE = "explore"
MODE_ISLAND = "island"
MODES = [MODE_RANDOM, MODE_EXPLORE, MODE_ISLAND]

MOODS = ["SLOW", "FAST", "WEIRD"]
# Random mode only accepts these; WEIRD is rejected by /play/random.
RANDOM_MOODS = ["SLOW", "FAST"]
DECADES = list(range(1900, 2030, 10))

# Fallback in case the track length is missing from the API response.
DEFAULT_TRACK_SECONDS = 240
# Output players briefly go idle while switching media; ignore that window.
SWITCH_GRACE_SECONDS = 8
# Extra wait past track length before forcing the next track.
END_SLACK_SECONDS = 15
# Idle within this many seconds of the end counts as "track finished".
END_TOLERANCE_SECONDS = 10

SCAN_INTERVAL = timedelta(hours=6)

SERVICE_PLAY = "play"

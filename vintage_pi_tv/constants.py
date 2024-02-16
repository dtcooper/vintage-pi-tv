import enum
from pathlib import Path


ENV_ARGS_VAR_NAME = "__VINTAGE_PI_TV_ARGS"
ENV_RELOAD_PID_NAME = "__VINTAGE_PI_TV_RELOAD_PID"

WHITE = (0xFF, 0xFF, 0xFF, 0xFF)
TRANSPARENT = (0x00, 0x00, 0x00, 0x00)
BLACK = (0x00, 0x00, 0x00, 0xFF)
BLACK_SEETHRU = (0x00, 0x00, 0x00, 0x55)
YELLOW = (0xFF, 0xEE, 0x00, 0xFF)
BLUE = (0x3A, 0xBF, 0xF8, 0xFF)
RED = (0xF8, 0x72, 0x72, 0xFF)
GREEN = (0x36, 0xD3, 0x99, 0xFF)

OSD_LAYER = 0
OSD_PROGRESS_BAR_LAYER = 1
OSD_VOLUME_LAYER = 2
OSD_NOTIFY_LAYER = 3
STATIC_LAYER = 10  # Above OSD
NO_FILES_LAYER = 62  # Second topmost
LOADING_LAYER = 63  # Topmost

DEFAULT_PORT = 6672


class PlayerState(enum.StrEnum):
    LOADING = "loading"
    NEEDS_FILES = "needs-files"
    PLAYING = "playing"
    PAUSED = "paused"


DATA_DIR = Path(__file__).absolute().parent / "data"

CHANNEL_MODE_RANDOM = "random"
CHANNEL_MODE_ALPHABETICAL = "alphabetical"
CHANNEL_MODE_CONFIG_ONLY = "config-only"
CHANNEL_MODE_CONFIG_FIRST_RANDOM = "config-first-random"
CHANNEL_MODE_CONFIG_FIRST_ALPHABETICAL = "config-first-alphabetical"
CHANNEL_MODES = (
    CHANNEL_MODE_RANDOM,
    CHANNEL_MODE_ALPHABETICAL,
    CHANNEL_MODE_CONFIG_ONLY,
    CHANNEL_MODE_CONFIG_FIRST_RANDOM,
    CHANNEL_MODE_CONFIG_FIRST_ALPHABETICAL,
)

DEFAULT_CONFIG_PATHS = (
    "/media/VintagePiTV/config.toml",
    "/boot/firmware/vintage-pi-tv-config.toml",  # In case third partition doesn't get created
    "./config.toml",
)

# Should match example-config.toml
DEFAULT_KEYBOARD_KEYS = {
    "down": "KEY_DOWN",
    "left": "KEY_LEFT",
    "mute": "KEY_0",
    "osd": "KEY_M",
    "pause": "KEY_P",
    "power": "KEY_ESC",
    "random": "KEY_ENTER",
    "ratings": "KEY_R",
    "rewind": "KEY_BACKSPACE",
    "right": "KEY_RIGHT",
    "up": "KEY_UP",
    "volume-down": "KEY_MINUS",
    "volume-up": "KEY_EQUAL",
}

# Should match example-config.toml
DEFAULT_IR_SCANCODES = {
    "down": 0xD2,
    "left": 0x99,
    "mute": False,
    "osd": 0x9D,
    "pause": 0xCE,
    "power": False,
    "random": 0xCB,
    "ratings": False,  # Would be 0x9C
    "rewind": 0x90,
    "right": 0xC1,
    "up": 0xCA,
    "volume-down": 0x81,
    "volume-up": 0x80,
}


DOCKER_DEV_KEYBOARD_KEYS = {
    # These match mpv keys, NOT ones defined by evdev in example-config.toml, use: $ mpv --input-keylist
    "down": "DOWN",
    "left": "LEFT",
    "mute": "0",
    "osd": "m",
    "pause": "p",
    "power": "ESC",
    "random": "ENTER",
    "ratings": "r",
    "rewind": "BS",
    "right": "RIGHT",
    "up": "UP",
    "volume-down": "-",
    "volume-up": "=",
}


DEFAULT_RATINGS = [
    {"rating": "G", "description": "General", "color": "#36D399"},  # The first will be the default rating of videos
    {"rating": "PG", "description": "Parental Guidance", "color": "#FFFFFF"},
    {"rating": "R", "description": "Restricted", "color": "#FFEE00"},
    {"rating": "X", "description": "Adult", "color": "#F87272"},  # The last will be the rating set on startup
]

# For Raspberry Pi
DEFAULT_MPV_OPTIONS = {
    "ao": "alsa",
    "fullscreen": "yes",
    "gpu-context": "drm",
    "hwdec": "auto-safe",
    "profile": "sw-fast",
    "vo": "gpu",
}

# For X11/Xwayland development
DEFAULT_DEV_MPV_OPTIONS = {
    **DEFAULT_MPV_OPTIONS,
    "geometry": "1280x720",  # 720p
    "ao": "pipewire,pulse,alsa",
    "fullscreen": "no",
    "gpu-context": "x11egl",
    "title": "Vintage Pi TV (dev mode)",
}

# For Docker development
DEFAULT_DOCKER_MPV_OPTIONS = {
    **DEFAULT_MPV_OPTIONS,
    "ao": "pulse,null",
    "gpu-context": "x11egl",
}

DEFAULT_AUDIO_FILE_EXTENSIONS = [
    "mp3",
    "wav",
    "aac",
    "flac",
    "ogg",
    "wma",
    "aiff",
    "m4a",
    "amr",
    "ac3",
    "mp2",
    "au",
    "ape",
    "opus",
    "dsf",
    "dff",
    "m4a",
    "mid",
    "ra",
    "wv",
    "mpc",
    "mpga",
    "spx",
    "mod",
    "awb",
    "mka",
]

DEFAULT_VIDEO_FILE_EXTENSIONS = [
    "mp4",
    "avi",
    "mkv",
    "mov",
    "wmv",
    "m4v",
    "flv",
    "3gp",
    "mpeg",
    "webm",
    "ogg",
    "asf",
    "vob",
    "divx",
    "xvid",
    "h264",
    "h265",
    "vp9",
    "avchd",
    "swf",
    "theora",
    "realvideo",
    "mxf",
    "cineform",
    "heif",
    "prores",
]

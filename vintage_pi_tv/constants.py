ENV_ARGS_VAR_NAME = "__VINTAGE_PI_TV_ARGS"

WHITE = (0xFF, 0xFF, 0xFF, 0xFF)
TRANSPARENT = (0x00, 0x00, 0x00, 0x00)
BLACK = (0x00, 0x00, 0x00, 0xFF)
BLACK_SEETHRU = (0x00, 0x00, 0x00, 0x44)

STATIC_LAYER = 0  # Lowest
NO_FILES_LAYER = 62  # Second topmost
LOADING_LAYER = 63  # Topmost

DEFAULT_CONFIG_PATHS = (
    "/media/VintagePiTV/config.toml",
    "/boot/firmware/vintage-pi-tv-config.toml",
    "./config.toml",
)

# Should match example-config.toml
DEFAULT_KEYBOARD_KEYS = {
    "back": "KEY_DELETE",
    "down": "KEY_DOWN",
    "enter": "KEY_ENTER",
    "home": "KEY_H",
    "left": "KEY_LEFT",
    "menu": "KEY_M",
    "mute": "KEY_0",
    "pause-resume": "KEY_P",
    "power": "KEY_ESC",
    "right": "KEY_RIGHT",
    "up": "KEY_UP",
    "volume-down": "KEY_MINUS",
    "volume-up": "KEY_EQUAL",
}

# Should match example-config.toml
DEFAULT_IR_SCANCODES = {
    "back": 0x90,
    "down": 0xD2,
    "enter": 0xCE,
    "home": 0xCB,
    "left": 0x99,
    "menu": 0x9D,
    "mute": False,
    "pause-resume": False,
    "power": False,  # Would be 0x9C
    "right": 0xC1,
    "up": 0xCA,
    "volume-down": 0x81,
    "volume-up": 0x80,
}

DEFAULT_RATINGS = [
    {"rating": "G", "description": "General"},
    {"rating": "PG", "description": "Parental Guidance"},
    {"rating": "R", "description": "Restricted"},
    {"rating": "X", "description": "Adult"},
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

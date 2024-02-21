from pathlib import Path

from schema import And, Optional, Or, Regex, Schema, SchemaError, Use

from .constants import (
    ASPECT_MODE_LETTERBOX,
    ASPECT_MODES,
    CHANNEL_MODE_RANDOM_DETERMINISTIC,
    CHANNEL_MODES,
    DEFAULT_DEV_MPV_OPTIONS,
    DEFAULT_DOCKER_MPV_OPTIONS,
    DEFAULT_IR_SCANCODES,
    DEFAULT_KEYBOARD_KEYS,
    DEFAULT_MPV_OPTIONS,
    DEFAULT_RATINGS,
    LOG_LEVELS,
)
from .keyboard import is_valid_key
from .utils import is_docker, is_raspberry_pi


NON_EMPTY_STRING = And(str, len)
NON_EMPTY_PATH = And(str, len, Use(lambda path: Path(path).expanduser().resolve()))
MPV_OPTION = Or(And(bool, Use(lambda val: "yes" if val else "no")), And(Use(str), len))


if is_docker():
    MPV_OPTIONS = DEFAULT_DOCKER_MPV_OPTIONS
elif is_raspberry_pi():
    MPV_OPTIONS = DEFAULT_MPV_OPTIONS
else:
    MPV_OPTIONS = DEFAULT_DEV_MPV_OPTIONS


class UniqueVideoNameSchema(Schema):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._values = set()

    def validate(self, data):
        data = super(UniqueVideoNameSchema, self).validate(data)
        if data in self._values:
            raise SchemaError(f"Non-unique filename in video list: {data}")
        self._values.add(data)
        return data


config_schema = Schema(
    {
        Optional("log-level", default="INFO", description=f"Log level, one of: {', '.join(LOG_LEVELS)}"): And(
            str,
            Use(lambda s: s.strip().lower()),
            Or(*LOG_LEVELS),
            Use(lambda s: s.upper()),
            error=f"Invalid 'log-level'. Must be one of {', '.join(LOG_LEVELS)}",
        ),
        Schema(
            "search-dirs",
            name="search-dirs",
            description=(
                "Directories to search for videos in. Must be a list of one or more strings OR dictionaries like `{"
                " path = <path>, recurse = <bool>, ignore = <bool> }`"
            ),
        ): And(
            len,
            [
                Or(
                    And(
                        {
                            "path": NON_EMPTY_PATH,
                            Optional("recurse", default=False): bool,
                            Optional("ignore", default=False): bool,
                        },
                        lambda d: not (d["recurse"] and d["ignore"]),
                    ),
                    And(
                        str,
                        len,
                        Use(
                            lambda path: {
                                "path": Path(path).expanduser().resolve(),
                                "recurse": False,
                                "ignore": False,
                            }
                        ),
                    ),
                )
            ],
            error=(
                "'search-dirs' must be a list of one or more string paths or `{{ path = <path>, recurse = <bool>,"
                " ignore = <bool> }}` style dictionaries. (NOTE: 'recurse' and 'ignore' can never both be set to true.)"
            ),
        ),
        Optional(
            "channel-mode",
            default=CHANNEL_MODE_RANDOM_DETERMINISTIC,
            description=f"Channel mode. Must be one of {', '.join(CHANNEL_MODES)}",
        ): And(
            str,
            Use(lambda s: s.strip().lower()),
            Or(*CHANNEL_MODES),
            error=f"Invalid 'channel-mode'. Must be one of {', '.join(CHANNEL_MODES)}",
        ),
        Optional("aspect-mode", default=ASPECT_MODE_LETTERBOX): And(
            str, Use(lambda s: s.strip().lower()), Or(*ASPECT_MODES)
        ),
        Optional("static-time", default=3.5): Or(
            And(Or(False, 0, 0.0), Use(lambda _: -1.0)), And(Use(float), lambda f: f > 0.0)
        ),
        Optional("show-fps", default=False): bool,
        Optional("channel-osd-always-on", default=False): bool,
        Optional("disable-osd", default=False): bool,
        Optional("save-place-while-browsing", default=True): bool,
        Optional("starting-volume", default=100): Or(False, And(int, lambda i: 0 <= i <= 100)),
        Optional("static-time-between-channels", default=0.5): Or(
            And(Or(False, 0, 0.0), Use(lambda _: -1.0)), And(Use(float), lambda f: f > 0.0)
        ),
        Optional("web-password", default=False): Or(False, NON_EMPTY_STRING),
        Optional("audio-visualization", default=True): bool,
        Optional("crt-filter", default=False): bool,
        Optional("subtitles-default-on", default=False): bool,
        Optional("power-key-shutdown", default="pi-only"): Or(bool, "pi-only"),
        Optional("ratings", default=DEFAULT_RATINGS): Or(
            False,
            And(
                [
                    Schema({
                        "rating": And(Use(str), Use(lambda s: s.strip().upper()), len),
                        "description": NON_EMPTY_STRING,
                        Optional("color", default="#FFFFFF"): Regex(r"^#[a-fA-F0-9]{6}$"),
                    })
                ],
                len,
            ),
        ),
        Optional("overscan-margins", default={"top": 0, "right": 0, "bottom": 0, "left": 0}): Or(
            Schema({direction: And(Use(int), lambda i: i >= 0) for direction in ("top", "right", "bottom", "left")}),
        ),
        Optional("valid-file-extensions", default="defaults"): Or([NON_EMPTY_STRING], "defaults"),
        Optional("mpv-options", default=MPV_OPTIONS): Schema({
            **{Optional(k, default=v): MPV_OPTION for k, v in MPV_OPTIONS.items()},
            # Catch-all for any other strings
            Optional(NON_EMPTY_STRING): NON_EMPTY_STRING,
        }),
        Optional("keyboard", default={"enabled": True, **DEFAULT_KEYBOARD_KEYS}): Schema({
            Optional("enabled", default=False): bool,
            **{
                Optional(k, default=v): Or(False, And(str, len, Use(lambda s: s.strip().upper()), is_valid_key))
                for k, v in DEFAULT_KEYBOARD_KEYS.items()
            },
        }),
        Optional("ir-remote", default={"enabled": False}): Schema({
            Optional("enabled", default=False): bool,
            Optional("protocol", default="nec"): str,
            Optional("variant", default="nec"): str,
            **{Optional(k, default=v): Or(False, int) for k, v in DEFAULT_IR_SCANCODES.items()},
        }),
        Optional("video", default=[]): [{
            "filename": UniqueVideoNameSchema(And(str, len, Use(lambda s: s.strip().lower()))),
            Optional("enabled", default=True): bool,
            Optional("name", default=""): And(Use(lambda s: s or ""), str, Use(lambda s: s.strip())),
            Optional("rating", default=False): Or(False, And(str, Use(lambda s: s.strip().upper()))),
            # Don't resolve subtitle symlink, since it's relative to file if not absolute
            Optional("subtitles", default=None): Or(
                bool, And(int, lambda i: i >= 1), And(str, len, Use(lambda path: Path(path).expanduser()))
            ),
        }],
    },
)

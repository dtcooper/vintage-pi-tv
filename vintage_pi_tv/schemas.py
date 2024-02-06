from pathlib import Path

from schema import And, Optional, Or, Schema, SchemaError, Use

from .constants import (
    DEFAULT_DEV_MPV_OPTIONS,
    DEFAULT_DOCKER_MPV_OPTIONS,
    DEFAULT_IR_SCANCODES,
    DEFAULT_KEYBOARD_KEYS,
    DEFAULT_MPV_OPTIONS,
    DEFAULT_RATINGS,
)
from .keyboard import is_valid_key
from .utils import is_docker, is_raspberry_pi


NON_EMPTY_STRING = And(str, len)
NON_EMPTY_PATH = And(str, len, Use(lambda path: Path(path).expanduser().resolve()))


if is_docker():
    mpv_options = DEFAULT_DOCKER_MPV_OPTIONS
elif is_raspberry_pi():
    mpv_options = DEFAULT_MPV_OPTIONS
else:
    mpv_options = DEFAULT_DEV_MPV_OPTIONS

mpv_options_schema = Schema({
    **{
        Optional(key, default=default): Or(And(bool, Use(lambda val: "yes" if val else "no")), NON_EMPTY_STRING)
        for key, default in mpv_options.items()
    },
    # Catch-all for any other strings
    Optional(NON_EMPTY_STRING): NON_EMPTY_STRING,
})


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
        Optional("log-level", default="INFO"): And(
            str,
            Use(lambda s: s.strip().upper()),
            Or("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"),
            error="Invalid 'log-level'. Must be one of 'critical', 'error', 'warning', 'info', or 'debug'.",
        ),
        Optional("channel-mode", default="random"): And(
            str,
            Use(lambda s: s.strip().lower()),
            Or("random", "alphabetical", "config-only", "config-first-random", "config-first-alphabetical"),
            error=(
                "Invalid 'channel-mode'. Must be one of 'random', 'alphabetical', 'config-only', "
                "'config-first-random', or 'config-first-alphabetical'"
            ),
        ),
        Optional("enable-audio-visualization", default=True): Use(bool),
        Optional("ratings", default=DEFAULT_RATINGS): Or(
            False,
            And(
                [
                    Schema({
                        "rating": And(Use(str), len, Use(lambda s: s.strip().upper())),
                        "description": NON_EMPTY_STRING,
                    })
                ],
                len,
            ),
        ),
        Optional("overscan-margins", default={"left": 0, "top": 0, "right": 0, "bottom": 0}): Or(
            Schema({direction: And(Use(int), lambda i: i >= 0) for direction in ("left", "top", "right", "bottom")}),
        ),
        "search-dirs": Schema(
            And(
                len,
                [
                    Or(
                        And(
                            {
                                "path": NON_EMPTY_PATH,
                                Optional("recurse", default=False): False,
                                Optional("ignore", default=False): False,
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
            ),
            error=(
                "'search-dirs' must be a list of one or more paths or {{ path = <path>, recurse = <bool>, ignore ="
                " <bool> }} style dictionaries. (NOTE: 'recurse' and 'ignore' can never both be set to true.)"
            ),
        ),
        Optional("valid-file-extensions", default="defaults"): Or([NON_EMPTY_STRING], "defaults"),
        Optional("mpv-options", default=mpv_options_schema.validate({})): mpv_options_schema,
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
            Optional("subtitles", default=False): Or(bool, NON_EMPTY_PATH),
        }],
    },
)

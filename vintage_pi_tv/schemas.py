import datetime
from pathlib import Path

from schema import And, Optional, Or, Schema, Use

from .constants import DEFAULT_RATINGS


NON_EMPTY_STRING = And(Use(str), len)


config_schema = Schema(
    {
        Optional("log_level", default="INFO"): And(
            Use(str),
            Use(lambda s: s.strip().upper()),
            Or("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"),
            error="Invalid 'log_level'. Must be one of 'critical', 'error', 'warning', 'info', or 'debug'.",
        ),
        Optional("videos_db_file", default=False): Or(False, Use(str)),
        Optional("enable_audio_with_visualization", default=True): Use(bool),
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
        "search_dirs": Schema(
            # No need to coerce path key into as Path object, since it's used a string with the
            # glob library
            [
                Or(
                    {
                        "path": NON_EMPTY_STRING,
                        Optional("recurse", default=False): False,
                        Optional("ignore", default=False): False,
                    },
                    {
                        "path": NON_EMPTY_STRING,
                        "recurse": True,
                        Optional("ignore", default=False): False,
                    },
                    {
                        "path": NON_EMPTY_STRING,
                        Optional("recurse", default=False): False,
                        "ignore": True,
                    },
                    And(str, len, Use(lambda path: {"path": path, "recurse": False, "ignore": False})),
                )
            ],
            error=(
                "'search_dirs' must be a list of paths or {{ path = <path>, recurse = <bool>, ignore = <bool> }} style"
                " dictionaries. NOTE: 'recurse' and 'ignore' cannot be both true."
            ),
        ),
        Optional("valid_file_extensions", default="defaults"): Or([NON_EMPTY_STRING], "defaults"),
        Optional("audio_driver", default="alsa"): NON_EMPTY_STRING,
        Optional("extra_mpv_options", default={}): Schema({NON_EMPTY_STRING: NON_EMPTY_STRING}),
    },
    ignore_extra_keys=True,
)

videos_schema = Schema({
    Optional("last_automatic_save", default=False): Or(False, datetime.datetime),
    And(Use(str), len, Use(Path)): Schema({
        Optional("enabled", default=True): Use(bool),
        Optional("name", default=""): And(Use(lambda s: s or ""), Use(str)),
        Optional("rating", default=False): Or(False, And(Use(str), Use(lambda s: s.strip().upper()))),
        Optional("subtitles", default=False): Or(bool, And(Use(str), len, Use(Path))),
    }),
})

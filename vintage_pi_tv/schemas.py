import datetime
from pathlib import Path
from typing import Literal

from schema import And, Optional, Or, Schema, Use

from .constants import DEFAULT_DEV_MPV_OPTIONS, DEFAULT_DOCKER_MPV_OPTIONS, DEFAULT_MPV_OPTIONS, DEFAULT_RATINGS


NON_EMPTY_STRING = And(Use(str), len)
NON_EMPTY_PATH = And(Use(str), len, Use(Path))


def generate_config_schema(dev_mode: Literal["docker"] | bool = False):
    if isinstance(dev_mode, str) and dev_mode == "docker":
        mpv_options = DEFAULT_DOCKER_MPV_OPTIONS
    elif dev_mode:
        mpv_options = DEFAULT_DEV_MPV_OPTIONS
    else:
        mpv_options = DEFAULT_MPV_OPTIONS

    mpv_options_schema = Schema({
        **{
            Optional(key, default=default): Or(And(bool, Use(lambda val: "yes" if val else "no")), NON_EMPTY_STRING)
            for key, default in mpv_options.items()
        },
        # Catch-all for any other strings
        Optional(NON_EMPTY_STRING): NON_EMPTY_STRING,
    })
    return Schema(
        {
            Optional("log_level", default="INFO"): And(
                Use(str),
                Use(lambda s: s.strip().upper()),
                Or("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"),
                error="Invalid 'log_level'. Must be one of 'critical', 'error', 'warning', 'info', or 'debug'.",
            ),
            Optional("videos_db_file", default=False): Or(False, Use(str)),
            Optional("enable_audio_visualization", default=True): Use(bool),
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
            Optional("overscan_margins", default=False): Or(
                False,
                Schema(
                    {direction: And(Use(int), lambda i: i >= 0) for direction in ("left", "top", "right", "bottom")}
                ),
            ),
            "search_dirs": Schema(
                And(
                    len,
                    [
                        Or(
                            {
                                "path": NON_EMPTY_PATH,
                                Optional("recurse", default=False): False,
                                Optional("ignore", default=False): False,
                            },
                            {
                                "path": NON_EMPTY_PATH,
                                "recurse": True,
                                Optional("ignore", default=False): False,
                            },
                            {
                                "path": NON_EMPTY_PATH,
                                Optional("recurse", default=False): False,
                                "ignore": True,
                            },
                            And(str, len, Use(lambda path: {"path": Path(path), "recurse": False, "ignore": False})),
                        )
                    ],
                ),
                error=(
                    "'search_dirs' must be a list of paths or {{ path = <path>, recurse = <bool>, ignore = <bool> }} "
                    " style dictionaries. NOTE: 'recurse' and 'ignore' cannot be both true."
                ),
            ),
            Optional("valid_file_extensions", default="defaults"): Or([NON_EMPTY_STRING], "defaults"),
            Optional("mpv_options", default=mpv_options_schema.validate({})): mpv_options_schema,
        },
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

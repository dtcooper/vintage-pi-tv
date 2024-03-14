import logging
from pathlib import Path
import queue
import tomllib
from typing import Any, Literal

from schema import SchemaError

from .constants import DEFAULT_AUDIO_FILE_EXTENSIONS, DEFAULT_VIDEO_FILE_EXTENSIONS
from .exceptions import InvalidConfigError
from .schemas import config_schema
from .utils import exit, is_raspberry_pi


logger = logging.getLogger(__name__)


class Config:
    aspect_mode: Literal["letterbox", "stretch", "zoom"]
    audio_visualization: bool | str
    channel_mode: Literal[
        "random",
        "random-deterministic",
        "alphabetical",
        "config-only",
        "config-first-random",
        "config-first-random-deterministic",
        "config-first-alphabetical",
    ]
    channel_osd_always_on: bool
    crt_filter: bool
    default_rating: bool | str
    disable_osd: bool
    ir_remote: dict[str, Any]
    keyboard: dict[str, Any]
    log_level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
    mpv_options: dict[str, str]
    overscan_margins: dict[str, int]
    password: Literal[False] | str
    ratings: list[dict[str, str]]
    power_key_shutdown: bool
    save_place_while_browsing: bool
    search_dirs: list[dict[str, Path | bool]]
    show_fps: bool
    starting_rating: bool | str
    starting_volume: int
    static_time_between_channels: float
    static_time: float
    subtitles_default_on: bool
    valid_file_extensions: set[str]
    videos: list[dict]

    def __init__(
        self,
        path: None | Path,
        websocket_updates_queue: None | queue.Queue = None,
        extra_search_dirs: list[Path] = (),
        log_level_override: None | str = None,
        **overrides,
    ):
        if path is None:
            toml = {}
        else:
            with open(path, "rb") as file:
                toml = tomllib.load(file)

        if log_level_override is not None:
            toml["log-level"] = log_level_override

        if overrides:
            toml.update({k.replace("_", "-"): v for k, v in overrides.items()})

        try:
            self._config = {k.replace("-", "_"): v for k, v in config_schema.validate(toml).items()}
            self._validate()
        except (SchemaError, InvalidConfigError) as e:
            logger.critical(f"Invalid configuration: {e}")
            exit(1, "Invalid configuration")

        self.search_dirs.extend(
            {"path": Path(path).expanduser().resolve(), "recurse": False, "ignore": False} for path in extra_search_dirs
        )

        if websocket_updates_queue is not None:
            websocket_updates_queue.put({"type": "ratings", "data": self.ratings})

    def _validate(self) -> None:
        if self.valid_file_extensions == "defaults":
            valid_extensions = list(DEFAULT_VIDEO_FILE_EXTENSIONS)
            if self.audio_visualization:
                valid_extensions.extend(DEFAULT_AUDIO_FILE_EXTENSIONS)
        self.valid_file_extensions = tuple(f".{ext}".lower() for ext in valid_extensions)
        self.ratings_dict: dict = {}
        if self.ratings:
            self.ratings_dict.update({rating["rating"]: {"num": n, **rating} for n, rating in enumerate(self.ratings)})
            if not self.starting_rating or self.starting_rating not in self.ratings_dict:
                self.starting_rating = self.ratings[-1]["rating"]
            self.default_rating = self.ratings[0]["rating"] if self.ratings else False
        else:
            self.starting_rating = False
            self.default_rating = False

        if self.disable_osd and self.channel_osd_always_on:
            logger.warning("'disable-osd' and 'channel_osd_always_on' both are true. Preferring 'disable-osd'")
            self.channel_osd_always_on = False

        # Resolve value to a boolean
        if isinstance(self.power_key_shutdown, str):
            self.power_key_shutdown = self.power_key_shutdown == "pi-only" and is_raspberry_pi()

        self.videos = {video.pop("filename"): video for video in self._config.pop("video")}

    def __getattr__(self, key):
        try:
            return self._config[key]
        except KeyError:
            raise AttributeError(f"Config has no value for {key}")

import logging
from pathlib import Path
import tomllib
from typing import Any, Literal

from schema import SchemaError

from .constants import DEFAULT_AUDIO_FILE_EXTENSIONS, DEFAULT_VIDEO_FILE_EXTENSIONS
from .exceptions import InvalidConfigError
from .schemas import config_schema
from .utils import exit


logger = logging.getLogger(__name__)


class Config:
    aspect_mode: Literal["letterbox", "stretch", "zoom"]
    channel_mode: Literal["random", "alphabetical", "config-only", "config-first-random", "config-first-alphabetical"]
    channel_osd_always_on: bool
    enable_audio_visualization: bool | str
    ir_remote: dict[str, Any]
    keyboard: dict[str, Any]
    log_level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
    mpv_options: dict[str, str]
    overscan_margins: dict[str, int]
    password: Literal[False] | str
    ratings: list[dict[str, str]]
    save_place_while_browsing: bool
    search_dirs: list[dict[str, Path | bool]]
    show_fps: bool
    start_muted: bool
    static_time_between_channels: float
    static_time: float
    valid_file_extensions: set[str]
    videos: list[dict]

    def __init__(self, path: None | Path, extra_search_dirs: tuple | list = (), log_level_override: None | str = None):
        if path is None:
            toml = {}
        else:
            with open(path, "rb") as file:
                toml = tomllib.load(file)

        # Add in extras
        toml.setdefault("search-dirs", []).extend(extra_search_dirs)
        if log_level_override is not None:
            toml["log-level"] = log_level_override

        try:
            self._config = {k.replace("-", "_"): v for k, v in config_schema.validate(toml).items()}
            self._validate()
        except (SchemaError, InvalidConfigError) as e:
            logger.critical(f"Invalid configuration: {e}")
            exit(1, "Invalid configuration")

    def _validate(self) -> None:
        if self.valid_file_extensions == "defaults":
            valid_extensions = list(DEFAULT_VIDEO_FILE_EXTENSIONS)
            if self.enable_audio_visualization:
                valid_extensions.extend(DEFAULT_AUDIO_FILE_EXTENSIONS)
        self.valid_file_extensions = tuple(f".{ext}".lower() for ext in valid_extensions)
        self.ratings_dict: dict[str, str] = {}
        if self.ratings:
            self.ratings_dict.update({rating["rating"]: {"num": n, **rating} for n, rating in enumerate(self.ratings)})

        self.videos = {video.pop("filename"): video for video in self._config.pop("video")}

    @property
    def default_rating(self) -> bool | str:
        return self.ratings[0]["rating"] if self.ratings else False

    @property
    def starting_rating(self) -> bool | str:
        return self.ratings[-1]["rating"] if self.ratings else False

    def __getattr__(self, key):
        try:
            return self._config[key]
        except KeyError:
            raise AttributeError(f"Config has no value for {key}")

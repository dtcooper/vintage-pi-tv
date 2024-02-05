import logging
from pathlib import Path
import sys
import tomllib
from typing import Literal

from schema import SchemaError

from .constants import DEFAULT_AUDIO_FILE_EXTENSIONS, DEFAULT_VIDEO_FILE_EXTENSIONS
from .exceptions import InvalidConfigError
from .schemas import config_schema


logger = logging.getLogger(__name__)


class Config:
    channel_mode: Literal["random", "alphabetical", "config-only", "config-first-random", "config-first-alphabetical"]
    enable_audio_visualization: bool | str
    log_level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
    mpv_options: dict[str, str]
    overscan_margins: list[int]
    ratings: list[dict[str, str]]
    search_dirs: list[dict[str, Path | bool]]
    valid_file_extensions: set[str]
    videos: list[dict]

    def __init__(self, path: None | Path, extra_search_dirs: tuple | list = ()):
        if path is None:
            toml = {"log-level": "debug"}
        else:
            with open(path, "rb") as file:
                toml = tomllib.load(file)

        # Add in extras
        toml.setdefault("search-dirs", []).extend(extra_search_dirs)

        try:
            self._config = {k.replace("-", "_"): v for k, v in config_schema.validate(toml).items()}
            self._validate()
        except (SchemaError, InvalidConfigError) as e:
            logger.critical(f"Invalid configuration: {e}")
            sys.exit(1)

    def _validate(self) -> None:
        if self.valid_file_extensions == "defaults":
            valid_extensions = list(DEFAULT_VIDEO_FILE_EXTENSIONS)
            if self.enable_audio_visualization:
                valid_extensions.extend(DEFAULT_AUDIO_FILE_EXTENSIONS)
        self.valid_file_extensions = tuple(f".{ext}".lower() for ext in valid_extensions)
        self.ratings_dict: dict[str, str] = {}
        if self.ratings:
            self.ratings_dict.update({rating["rating"]: rating["description"] for rating in self.ratings})

        self.videos = {video.pop("filename"): video for video in self._config.pop("video")}
        print(self.videos)

    @property
    def default_rating(self) -> bool | str:
        return self.ratings[0]["rating"] if self.ratings else False

    def __getattr__(self, key):
        try:
            return self._config[key]
        except KeyError:
            raise AttributeError(f"Config has no value for {key}")

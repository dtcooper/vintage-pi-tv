import logging
import os
from pathlib import Path
import sys
from typing import Literal

from schema import SchemaError
import tomlkit

from .constants import DEFAULT_AUDIO_FILE_EXTENSIONS, DEFAULT_VIDEO_FILE_EXTENSIONS
from .exceptions import InvalidConfigError
from .schemas import config_schema


logger = logging.getLogger(__name__)


class Config:
    audio_driver: str
    enable_audio_visualization: bool | str
    extra_mpv_options: dict[str, str]
    log_level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
    ratings: list[dict[str, str]]
    search_dirs: list[dict[str, Path | bool]]
    valid_file_extensions: set[str]
    video_driver: str
    videos_db_file: bool | Path

    def __init__(self, path: "os.PathLike"):
        self.config_path = Path(path)
        with open(self.config_path) as file:
            toml = tomlkit.load(file)

        try:
            self._config = config_schema.validate(toml.unwrap())
            self.validate()
        except (SchemaError, InvalidConfigError) as e:
            logger.critical(f"Invalid configuration: {e}")
            sys.exit(1)

    def validate(self) -> None:
        if self.videos_db_file:
            self.videos_db_file = Path(self.videos_db_file)
            if not self.videos_db_file.is_absolute():
                # Set path relative to config file
                self.videos_db_file = self.config_path.parent / self.videos_db_file

        if self.valid_file_extensions == "defaults":
            valid_extensions = list(DEFAULT_VIDEO_FILE_EXTENSIONS)
            if self.enable_audio_visualization:
                valid_extensions.extend(DEFAULT_AUDIO_FILE_EXTENSIONS)
        self.valid_file_extensions = {f".{ext}".lower() for ext in valid_extensions}
        self.ratings_dict: dict[str, str] = {}
        if self.ratings:
            self.ratings_dict.update({rating["rating"]: rating["description"] for rating in self.ratings})

    @property
    def default_rating(self) -> bool | str:
        return self.ratings[0]["rating"] if self.ratings else False

    def __getattr__(self, key):
        try:
            return self._config[key]
        except KeyError:
            raise AttributeError(f"Config has no value for {key}")

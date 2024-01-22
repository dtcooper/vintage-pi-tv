import datetime
import glob
import logging
import os
from pathlib import Path
import random
from typing import Any

from schema import SchemaError
import tomlkit

from .config import Config
from .constants import DATETIME_FORMAT
from .schemas import videos_schema
from .utils import listdir_recursive


logger = logging.getLogger(__name__)


class Video:
    def __init__(
        self, path: Path, config: Config, name: str, enabled: bool, rating: bool | str, subtitles: bool | Path
    ):
        self.path = path
        self.config = config
        self.name = name.strip()
        if not self.name:
            self.name = self.get_automatic_name(path)
        self.enabled = enabled
        self.rating = rating
        if rating and rating in config.ratings_dict:
            self.rating = rating
        else:
            self.rating = config.default_rating
        self.subtitles = subtitles
        self.channel: int | None = None  # Set manually by VideosDB

    @staticmethod
    def get_automatic_name(path: Path) -> str:
        return path.stem.strip().replace("-", " ").replace("_", " ").title()

    def to_toml(self) -> tuple[str, dict[str, Any]]:
        metadata: dict[str, Any] = {"name": self.name}
        if self.rating != self.config.default_rating:  # If it's not the default, save it
            metadata["rating"] = self.rating
        if not self.enabled:
            metadata["enabled"] = False
        if self.subtitles:
            metadata["subtitles"] = str(self.subtitles) if isinstance(self.subtitles, Path) else self.subtitles
        return (str(self.path), metadata)


class VideosDB:
    def __init__(self, config: Config):
        self.config: Config = config
        self.videos: dict[Path, Video] = {}
        self.toml: "tomlkit.TOMLDocument" = tomlkit.TOMLDocument()

        self.init_videos_db()

    def load_videos_db(self):
        if self.config.videos_db_file:
            try:
                with open(self.config.videos_db_file) as file:
                    self.toml = tomlkit.load(file)
                videos = videos_schema.validate(self.toml.unwrap())
                last_saved = videos.pop("last_automatic_save")
                last_saved = last_saved.strftime(DATETIME_FORMAT) if last_saved else "unknown"
            except SchemaError as e:
                logger.error(f"Error parsing video 'videos_db_file', disabling the use of config file: {e}")
                self.config.videos_db_file = False
            except Exception:
                logger.exception(f"Error opening 'videos_db_file' {self.config.videos_db_file}")
            else:
                self.videos.update({path: Video(path, self.config, **metadata) for path, metadata in videos.items()})
                logger.info(f"Loaded {len(self.videos)} video(s) from {last_saved} from {self.config.videos_db_file}")
        else:
            logger.info("'videos_db_file' set to false")

    def save_videos_db(self) -> None:
        if self.config.videos_db_file:
            save_time = datetime.datetime.now().replace(microsecond=0)
            self.toml["last_automatic_save"] = save_time
            temp_file = self.config.videos_db_file.parent / f"{self.config.videos_db_file.name}.tmp"
            try:
                with open(temp_file, "w") as file:
                    tomlkit.dump(self.toml, file)
                os.rename(temp_file, self.config.videos_db_file)
                logger.info(
                    f"Saved {len(self.toml) - 1} videos to {self.config.videos_db_file} at"
                    f" {save_time.strftime(DATETIME_FORMAT)}"
                )
            except Exception:
                logger.exception(f"Error saving 'videos_db_file' {self.config.videos_db_file}. Disabling saving.")
                self.config.videos_db_file = False
        else:
            logger.debug("Skipping videos db save since 'videos_db_file' is false")

    def init_videos_db(self) -> None:
        search_dirs: set[Path] = set()
        exclude_dirs: set[Path] = set()
        recurse: dict[Path, bool] = {}

        # Build directories to search in and directories to ignore
        for info in self.config.search_dirs:
            for path in map(Path, glob.glob(str(info["path"].expanduser()), root_dir="/")):
                if path.is_dir():
                    if info["ignore"]:
                        exclude_dirs.add(path)
                    else:
                        search_dirs.add(path)
                        recurse[path] = info["recurse"]
                else:
                    logger.warning(f"Path in 'search_dirs' {path} is not a directory. Skipping.")

        search_dirs = search_dirs - exclude_dirs
        for path in search_dirs:
            logger.info(f"Adding search path {path}{' (recursive)' if recurse[path] else ''}")
        for path in exclude_dirs:
            logger.info(f"Adding ignore path {path}")

        # Find all videos contained with in the directories to search
        video_files: set[Path] = set()
        for search_dir in search_dirs:
            listdir = listdir_recursive if recurse[search_dir] else os.listdir
            dir_contents = ((search_dir / p) for p in listdir(search_dir))
            for path in dir_contents:
                if path.is_file() and any(path.name.lower().endswith(ext) for ext in self.config.valid_file_extensions):
                    video_files.add(path)
                else:
                    logger.debug(f"Ignoring file: {path}")

        self.load_videos_db()

        # Existing videos (lower channels, dictionaries in Python >= 3.6 retain their ordering)
        for video in self.videos.values():
            logger.debug(f"Found existing video: {path}")
            if not video.path.is_file():
                video.enabled = False
            self.write_video_to_db(video, skip_write=True)

        # Discovered videos on disk (higher channels, after lower ones)
        num_found = 0
        for path in sorted(video_files):
            if path not in self.videos:  # Already exists
                num_found += 1
                logger.debug(f"Found new video: {path}")
                video = self.videos[path] = Video(
                    path, self.config, name="", enabled=True, rating=False, subtitles=False
                )
                self.write_video_to_db(video, skip_write=True)

        logger.info(f"Found {num_found} new video(s) from 'search_dirs'")

        # Assign channels and ratings
        channel = 1
        for video in self.videos.values():
            if video.enabled:
                video.channel = channel
                logger.debug(f"Assigning channel {channel} to {video.path}")
                channel += 1

        logger.info(f"Found {len(self.videos)} video(s)")
        self.save_videos_db()

    def write_video_to_db(self, video: Video, skip_write: bool = False):
        path, metadata = video.to_toml()
        if path in self.toml:
            self.toml[path].update(metadata)  # Update in place, preserves comments/whitespace
        else:
            self.toml[path] = metadata
            self.toml[path].trivia.comment = f"# Added at {datetime.datetime.now().strftime(DATETIME_FORMAT)}"
            self.toml[path].trivia.comment_ws = "  "

        if not skip_write:
            self.save_videos_db()

    def get_next_video(self):
        return random.choice(list(self.videos.values()))

import logging
import os
from pathlib import Path
import random
import sys
import threading

import watchfiles

from .config import Config
from .utils import listdir_recursive


logger = logging.getLogger(__name__)


class Video:
    def __init__(
        self,
        config: Config,
        path: Path,
        channel: int,
        name: str | None,
        rating: bool | str,
        subtitles: bool | Path,
    ):
        self._config = config

        self.path = path
        self.channel = channel
        self.name = name or self.get_automatic_video_name()
        self.rating = rating
        if not self.rating or self.rating not in self._config.ratings_dict:
            self.rating = config.default_rating
        self.subtitles = subtitles

    @staticmethod
    def get_automatic_video_name(path: Path) -> str:
        return path.stem.strip().replace("-", " ").replace("_", " ").title()

    def __repr__(self):
        return f"Video(name={self.name!r}, path={self.path!r}, channel={self.channel})"


class VideosDB:
    def _init_dirs(self):
        self._search_dirs = list()
        self._search_dirs_recursive = list()
        self._exclude_dirs = list()

        for info in self._config.search_dirs:

            if info["ignore"]:
                logger.debug(f"Adding ignore dir: {info['path']}")
                self._exclude_dirs.append(info["path"])
            if info["path"].is_dir():
                if info["recurse"]:
                    logger.debug(f"Adding recursive search dir: {info['path']}")
                    self._search_dirs_recursive.append(info["path"])
                else:
                    logger.debug(f"Adding search dir: {info['path']}")
                    self._search_dirs.append(info["path"])
            else:
                logger.warning(f"Path in 'search_dirs' {info['path']} is not a directory. Skipping.")

        if not self._search_dirs and not self._search_dirs_recursive:
            logger.critical("No search_dirs are actually valid directories.")
            sys.exit(1)

        logger.info(
            f"Added {len(self._search_dirs) + len(self._search_dirs_recursive)} search dirs,"
            f" {len(self._exclude_dirs)} exclude dirs"
        )

    def _is_valid_video_path(self, path: Path):
        # Ends with a valid extension
        if not path.name.strip().lower().endswith(self._config.valid_file_extensions):
            return False

        for exclude_dir in self._exclude_dirs:
            # If the path is a subdirectory of an exclude dir
            if path.is_relative_to(exclude_dir):
                for search_dir in self._search_dirs + self._search_dirs_recursive:
                    # There is path is a subdirectory of a search dir and that search dir is a subdirectory of the
                    # exclude dir. In this case, we explicitly DO NOT ignore this file.
                    if path.is_relative_to(search_dir) and search_dir.is_relative_to(exclude_dir):
                        logger.debug(
                            f"Path {path} would have been filtered by exclude dir {exclude_dir}, but search dir"
                            f" {search_dir} exists after it"
                        )
                        break
                else:
                    logger.debug(f"Path {path} was filtered by exclude dir: {exclude_dir}")
                    return False

        return True

    def queue_channel_rebuild(self):
        with self._rebuild_channel_lock:
            self._wants_channel_rebuild = True

    def rebuild_channels_if_needed(self):
        # Make sure this gets checked and modified automically
        with self._rebuild_channel_lock:
            if not self._wants_channel_rebuild:
                return
            self._wants_channel_rebuild = False

        logger.info("Rebuilding channel list...")

        videos = []  # List of kwargs for video objects
        seen_paths = set()

        for search_dirs, listdir in ((self._search_dirs, os.listdir), (self._search_dirs_recursive, listdir_recursive)):
            for search_dir in search_dirs:
                for path in ((search_dir / filename) for filename in listdir(search_dir)):
                    if path in seen_paths:
                        continue
                    seen_paths.add(path)

                    if path.is_file() and self._is_valid_video_path(path):
                        filename = path.name.strip().lower()
                        from_config = False
                        video = {"path": path, "name": "", "enabled": True, "subtitles": False, "rating": False}
                        config_metadata = self._config.videos.get(filename)
                        if config_metadata is not None:
                            from_config = True
                            video.update(config_metadata)
                        if not video["name"]:
                            video["name"] = Video.get_automatic_video_name(path)
                        # Format: (<found from config bool>, <video kwargs>)
                        videos.append((from_config, video))
                        if video["enabled"]:
                            logger.debug(f"Found video {path} [name={video['name']!r}] [found in config={from_config}]")
                        else:
                            logger.debug(f"Ignoring video {path} as enabled=False")

        def channel_sort_key(from_config_video):
            _, video = from_config_video
            return (video["name"], video["path"])

        logger.info(f"Sorting channels by mode: {self._config.channel_mode}")

        # Sort by channel mode
        if self._config.channel_mode == "random":
            random.shuffle(videos)
        elif self._config.channel_mode == "alphabetical":
            videos.sort(key=channel_sort_key)
        else:
            videos_config = [v for v in videos if v[0]]
            if self._config.channel_mode == "config-only":
                videos = videos_config
            else:
                videos_non_config = [v for v in videos if not v[0]]
                if self._config.channel_mode == "config-first-random":
                    random.shuffle(videos_non_config)
                elif self._config.channel_mode == "config-first-alphabetical":
                    videos_non_config.sort(key=channel_sort_key)
                videos = videos_config + videos_non_config

        videos = filter(lambda v: v.pop("enabled"), map(lambda v: v[1], videos))
        self.videos = [Video(config=self._config, channel=channel, **video) for channel, video in enumerate(videos, 1)]
        logger.info(f"Generated {len(self.videos)} channels")

    def get_next_video(self) -> Video:
        return random.choice(self.videos)

    def _watch_thread(self, search_dirs, recursive):
        logger.info(f"Starting search_dirs watching thread {recursive=}")

        for changes in watchfiles.watch(
            *search_dirs, watch_filter=lambda _, path: self._is_valid_video_path(Path(path))
        ):
            logger.info("Detected file change(s). Queuing for channel rebuild.")
            for change, path in changes:
                logger.debug(f"Detected file change ({change.name}): {path}")
            with self._rebuild_channel_lock:
                self._wants_channel_rebuild = True

    def __init__(self, config: Config):
        self.channels: list[Video] = []
        self._config: Config = config
        self._search_dirs: list[Path] = []
        self._search_dirs_recursive: list[Path] = []
        self._exclude_dirs: list[Path] = []
        self._wants_channel_rebuild: bool = True
        self._rebuild_channel_lock: threading.Lock = threading.Lock()

        self._init_dirs()
        self.rebuild_channels_if_needed()
        if self._search_dirs:
            thread = threading.Thread(target=self._watch_thread, args=(self._search_dirs, False), daemon=True)
            thread.start()
        if self._search_dirs_recursive:
            thread = threading.Thread(target=self._watch_thread, args=(self._search_dirs_recursive, False), daemon=True)
            thread.start()
        logger.info("Videos DB fully initialized")

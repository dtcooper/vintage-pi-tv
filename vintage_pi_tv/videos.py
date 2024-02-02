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
        self.config = config

        self.path = path
        self.channel = channel
        self.name = name or self.get_automatic_video_name()
        self.rating = rating
        if not self.rating or self.rating not in config.ratings_dict:
            self.rating = config.default_rating
        self.subtitles = subtitles

    @staticmethod
    def get_automatic_video_name(path: Path) -> str:
        return path.stem.strip().replace("-", " ").replace("_", " ").title()

    def __repr__(self):
        return f"Video(name={self.name!r}, path={self.path!r}, channel={self.channel})"


class VideosDB:
    def _init_dirs(self):
        self.search_dirs = list()
        self.search_dirs_recursive = list()
        self.exclude_dirs = list()

        for info in self.config.search_dirs:
            if info["path"].is_dir():
                if info["ignore"]:
                    logger.debug(f"Adding ignore dir: {info['path']}")
                    self.exclude_dirs.append(info["path"])
                elif info["recurse"]:
                    logger.debug(f"Adding recursive search dir: {info['path']}")
                    self.search_dirs_recursive.append(info["path"])
                else:
                    logger.debug(f"Adding search dir: {info['path']}")
                    self.search_dirs.append(info["path"])
            else:
                logger.warning(f"Path in 'search_dirs' {info['path']} is not a directory. Skipping.")

        if not self.search_dirs and not self.search_dirs_recursive:
            logger.critical("No search_dirs are actually valid directories.")
            sys.exit(1)

        logger.info(
            f"Added {len(self.search_dirs) + len(self.search_dirs_recursive)} search dirs,"
            f" {len(self.exclude_dirs)} exclude dirs"
        )

    def is_valid_path(self, path):
        return path.name.lower().endswith(self.config.valid_file_extensions) and not any(
            exclude_dir in path.parents for exclude_dir in self.exclude_dirs
        )

    def queue_channel_rebuild(self):
        with self.rebuild_channel_lock:
            self.wants_channel_rebuild = True

    def rebuild_channels_if_needed(self):
        # Make sure this gets checked and modified automically
        with self.rebuild_channel_lock:
            if not self.wants_channel_rebuild:
                return
            self.wants_channel_rebuild = False

        logger.info("Rebuilding channel list...")

        videos = []  # List of kwargs for video objects

        for search_dirs, listdir in ((self.search_dirs, os.listdir), (self.search_dirs_recursive, listdir_recursive)):
            for search_dir in search_dirs:
                for path in ((search_dir / filename) for filename in listdir(search_dir)):
                    if path.is_file() and self.is_valid_path(path):
                        filename = path.name.strip().lower()
                        from_config = False
                        video = {"path": path, "name": "", "enabled": True, "subtitles": False, "rating": False}
                        config_metadata = self.config.videos.get(filename)
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

        logger.info(f"Sorting channels by mode: {self.config.channel_mode}")

        # Sort by channel mode
        if self.config.channel_mode == "random":
            random.shuffle(videos)
        elif self.config.channel_mode == "alphabetical":
            videos.sort(key=channel_sort_key)
        else:
            videos_config = [v for v in videos if v[0]]
            if self.config.channel_mode == "config-only":
                videos = videos_config
            else:
                videos_non_config = [v for v in videos if not v[0]]
                if self.config.channel_mode == "config-first-random":
                    random.shuffle(videos_non_config)
                elif self.config.channel_mode == "config-first-alphabetical":
                    videos_non_config.sort(key=channel_sort_key)
                videos = videos_config + videos_non_config

        videos = filter(lambda v: v.pop("enabled"), map(lambda v: v[1], videos))
        self.videos = [Video(config=self.config, channel=channel, **video) for channel, video in enumerate(videos, 1)]
        logger.info(f"Generated {len(self.videos)} channels")

    def get_next_video(self) -> Video:
        return random.choice(self.videos)

    def watch_thread(self, search_dirs, recursive):
        logger.info(f"Starting search_dirs watching thread {recursive=}")

        for changes in watchfiles.watch(*search_dirs, watch_filter=lambda _, path: self.is_valid_path(Path(path))):
            logger.info("Detected file change(s). Queuing for channel rebuild.")
            for change, path in changes:
                logger.debug(f"Detected file change ({change.name}): {path}")
            self.queue_channel_rebuild()

    def __init__(self, config: Config):
        self.channels: list[Video] = []
        self.config: Config = config
        self.search_dirs: list[Path] = []
        self.search_dirs_recursive: list[Path] = []
        self.exclude_dirs: list[Path] = []
        self.wants_channel_rebuild: bool = True
        self.rebuild_channel_lock: threading.Lock = threading.Lock()

        self._init_dirs()
        self.rebuild_channels_if_needed()
        if self.search_dirs:
            thread = threading.Thread(target=self.watch_thread, args=(self.search_dirs, False), daemon=True)
            thread.start()
        if self.search_dirs_recursive:
            thread = threading.Thread(target=self.watch_thread, args=(self.search_dirs_recursive, False), daemon=True)
            thread.start()
        logger.info("Videos DB fully initialized")

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
        videos_db: "VideosDB",
        path: Path,
        name: str | None,
        rating: bool | str,
        subtitles: bool | Path,
    ):
        self._videos_db = videos_db

        self.path = path
        self.name = name or self.get_automatic_video_name()
        self.rating = rating
        if not self.rating or self.rating not in self._videos_db.config.ratings_dict:
            self.rating = self._videos_db.config.default_rating
        self.subtitles = subtitles

    @staticmethod
    def get_automatic_video_name(path: Path) -> str:
        return path.stem.strip().replace("-", " ").replace("_", " ").title()

    @property
    def channel(self) -> int:
        return self._videos_db.channels.get(self.path, -1)

    @property
    def display_channel(self) -> int:
        return self.channel + 1

    def serialize(self):
        return {"path": str(self.path), "channel": self.channel + 1, "rating": self.rating, "name": self.name}

    def __repr__(self):
        return f"Video(name={self.name!r}, path={self.path!r}, channel={self.channel})"


class VideosDB:
    def __init__(self, config: Config):
        self.config: Config = config
        self._search_dirs: list[Path] = []
        self._search_dirs_recursive: list[Path] = []
        self._exclude_dirs: list[Path] = []
        self._wants_channel_rebuild: bool = True
        self._rebuild_event: threading.Event = threading.Event()
        self._channel_lock: threading.Lock = threading.Lock()
        self.watch_stop_event = threading.Event()
        self.has_videos_event = threading.Event()

        self._init_dirs()
        self._rebuild_channels()

        logger.info("Videos DB fully initialized")

    def _init_dirs(self):
        self._bad_video_paths = set()
        self._search_dirs = list()
        self._search_dirs_recursive = list()
        self._exclude_dirs = list()

        for info in self.config.search_dirs:
            if info["ignore"]:
                logger.debug(f"Adding ignore dir: {info['path']}")
                self._exclude_dirs.append(info["path"])
            elif info["path"].is_dir():
                if info["recurse"]:
                    logger.debug(f"Adding recursive search dir: {info['path']}")
                    self._search_dirs_recursive.append(info["path"])
                else:
                    logger.debug(f"Adding search dir: {info['path']}")
                    self._search_dirs.append(info["path"])
            else:
                logger.warning(f"Path in 'search-dirs' {info['path']} is not a directory. Skipping.")

        if not self._search_dirs and not self._search_dirs_recursive:
            logger.critical("No search-dirs are actually valid directories.")
            sys.exit(1)

        logger.info(
            f"Added {len(self._search_dirs) + len(self._search_dirs_recursive)} search dirs,"
            f" {len(self._exclude_dirs)} ignore dirs"
        )

    def _is_valid_video_path(self, path: Path):
        # Ends with a valid extension
        if not path.name.strip().lower().endswith(self.config.valid_file_extensions):
            return False

        if path in self._bad_video_paths:
            logger.trace(f"Video at {path} was marked bad. Filtering.")
            return False

        for exclude_dir in self._exclude_dirs:
            # If the path is a subdirectory of an exclude dir
            if path.is_relative_to(exclude_dir):
                for search_dir in self._search_dirs:
                    if path.parent == search_dir and search_dir.relative_to(exclude_dir):
                        logger.trace(
                            f"Path {path} would have been filtered by exclude dir {exclude_dir}, but search dir"
                            f" {search_dir} exists higher in the directory tree (after it)"
                        )
                        break
                else:
                    for search_dir in self._search_dirs_recursive:
                        # There is path is a subdirectory of a search dir and that search dir is a subdirectory of the
                        # exclude dir. In this case, we explicitly DO NOT ignore this file.
                        if path.is_relative_to(search_dir) and search_dir.is_relative_to(exclude_dir):
                            logger.trace(
                                f"Path {path} would have been filtered by exclude dir {exclude_dir}, but recursive"
                                f" search dir {search_dir} exists higher in the directory tree (after it)"
                            )
                            break
                    else:
                        logger.trace(f"Path {path} was filtered by exclude dir: {exclude_dir}")
                        return False

        logger.trace(f"Path {path} is a valid video path")
        return True

    def _rebuild_channels(self):
        logger.info("Rebuilding channel list...")

        videos = []  # List of kwargs for video objects
        seen_paths = set()
        ignored_files = 0

        for search_dirs, listdir in ((self._search_dirs, os.listdir), (self._search_dirs_recursive, listdir_recursive)):
            for search_dir in search_dirs:
                for path in ((search_dir / filename) for filename in listdir(search_dir)):
                    if path in seen_paths:
                        continue
                    seen_paths.add(path)

                    if path.is_file():
                        if self._is_valid_video_path(path):
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
                            if video["enabled"]:
                                del video["enabled"]
                                videos.append((from_config, video))
                                logger.debug(f"Found video {path} [name={video['name']!r}] [{from_config=}]")
                            else:
                                logger.debug(f"Ignoring video {path} as enabled=False")
                                ignored_files += 1
                        else:
                            ignored_files += 1

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
                else:
                    raise Exception("Invalid 'channel-mode' (should never get here!)")
                videos = videos_config + videos_non_config

        videos = [Video(videos_db=self, **v) for (_, v) in videos]
        # Operation should be atomic, assign both at same time
        with self._channel_lock:
            self._videos = {"objects": videos, "channels": {v.path: i for i, v in enumerate(videos)}}
            logger.info(f"Generated {len(self.videos)} channels, ignored {ignored_files} files")
            if videos:
                self.has_videos_event.set()
            else:
                self.has_videos_event.clear()

    @property
    def videos(self) -> list[Video]:
        return self._videos["objects"]

    @property
    def channels(self) -> dict[Path, int]:
        return self._videos["channels"]

    def get_random_video(self) -> Video:
        with self._channel_lock:  # Prevents self.videos from being modified while working here
            if self.videos:
                video = random.choice(self.videos)
                logger.debug(f"Randomly chose video {video.path}")
            else:
                video = None

        return video

    def get_video_for_channel(self, channel: int) -> Video:
        with self._channel_lock:  # Prevents self.videos from being modified while working here
            num_channels = len(self.channels)
            if num_channels == 0:
                return None
            return self.videos[channel % num_channels]

    def rebuild_channels_thread(self):
        while True:
            self._rebuild_event.wait()
            self._rebuild_event.clear()
            self._rebuild_channels()

    def _watch_thread_helper(self, search_dirs: list[Path], recursive: bool):
        for changes in watchfiles.watch(
            *search_dirs,
            stop_event=self.watch_stop_event,
            watch_filter=lambda _, path: self._is_valid_video_path(Path(path)),
        ):
            logger.info("Detected file change(s). Queuing for channel rebuild.")
            for change, path in changes:
                logger.debug(f"Detected file change ({change.name}): {path}")
            self._rebuild_event.set()

    def watch_thread(self, recursive: bool):
        search_dirs = self._search_dirs_recursive if recursive else self._search_dirs
        if search_dirs:
            self._watch_thread_helper(search_dirs, recursive)
        else:
            logger.debug(f"No need to start watch-dirs thread for {recursive=}")

    def mark_bad_video(self, video: Video) -> None:
        self._bad_video_paths.add(video.path)
        self._rebuild_event.set()

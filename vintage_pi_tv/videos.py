import logging
import os
from pathlib import Path
import queue
import random
import threading
import time
from typing import Literal

import watchfiles

from .config import Config
from .constants import (
    CHANNEL_MODE_ALPHABETICAL,
    CHANNEL_MODE_CONFIG_FIRST_ALPHABETICAL,
    CHANNEL_MODE_CONFIG_FIRST_RANDOM,
    CHANNEL_MODE_CONFIG_FIRST_RANDOM_DETERMINISTIC,
    CHANNEL_MODE_CONFIG_ONLY,
    CHANNEL_MODE_RANDOM,
    CHANNEL_MODE_RANDOM_DETERMINISTIC,
)
from .utils import exit, listdir_recursive, normalize_filename, shuffle_deterministic


logger = logging.getLogger(__name__)


class Video:
    def __init__(
        self,
        videos_db: "VideosDB",
        path: Path,
        name: str | None,
        rating: str | Literal[False],
        subtitles: None | int | bool | Path,
        from_config: bool = False,
    ):
        self._videos_db = videos_db

        self.path: Path = path
        self.name: str = name or self.get_automatic_video_name()

        default_rating = self._videos_db.config.default_rating
        self.rating_dict: None | dict
        self.rating: str | Literal[False] = rating or default_rating  # Assign default if falsey
        if self.rating:  # Default could be false (in which case ratings are disabled)
            if self.rating not in self._videos_db.config.ratings_dict:
                logger.warning(
                    f"Video {path} had an invalid rating: {self.rating!r}. Assigning default: {default_rating!r}"
                )
                self.rating = default_rating
            self.rating_dict = self._videos_db.config.ratings_dict[self.rating]

        self.subtitles: int | Path
        if subtitles is None:  # Unset
            self.subtitles = 1 if self._videos_db.config.subtitles_default_on else False
        elif isinstance(subtitles, Path):  # Path, relative or absolute
            if subtitles.is_absolute():
                self.subtitles = subtitles
            else:
                self.subtitles = self.path.parent / subtitles
        elif isinstance(subtitles, bool):  # bool
            self.subtitles = 1 if subtitles else False
        else:  # int (will be greater than 0 from schema)
            self.subtitles = subtitles

        self.from_config: bool = from_config  # Used in __main__:generate_videos_config

    @staticmethod
    def get_automatic_video_name(path: Path) -> str:
        return path.stem.strip().replace("-", " ").replace("_", " ").title()

    @property
    def filename(self) -> str:
        return normalize_filename(self.path)

    @property
    def channel(self) -> int:
        return self._videos_db.channels.get(self.path, -1)

    @property
    def display_channel(self) -> str:
        return self.channel + 1

    def is_viewable_based_on_rating(self, rating):
        return not rating or self.rating_dict["num"] <= self._videos_db.config.ratings_dict[rating]["num"]

    def serialize(self) -> dict:
        return {
            "path": str(self.path),
            "channel": self.display_channel,
            "rating": self.rating,
            "name": self.name,
            "filename": self.filename,
        }

    def __repr__(self):
        return f"Video(name={self.name!r}, path={self.path!r}, channel={self.channel})"


class VideosDB:
    def __init__(self, config: Config, websocket_updates_queue: None | queue.Queue = None):
        self.config: Config = config
        self._search_dirs: list[Path] = []
        self._search_dirs_recursive: list[Path] = []
        self._exclude_dirs: list[Path] = []
        self._wants_channel_rebuild: bool = True
        self._rebuild_event: threading.Event = threading.Event()
        self._channel_lock: threading.Lock = threading.Lock()
        self.watch_stop_event: threading.Event = threading.Event()
        self.has_videos_event: threading.Event = threading.Event()
        self._websocket_updates_queue: queue.Queue = websocket_updates_queue

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
            logger.critical("No 'search-dirs' are actually valid directories.")
            exit(1, "Videos DB failed to initialize (no search dirs)")

        logger.info(
            f"Added {len(self._search_dirs) + len(self._search_dirs_recursive)} search dirs,"
            f" {len(self._exclude_dirs)} ignore dirs"
        )

    def _is_valid_video_path(self, path: Path, filter_by_extension: bool = True):
        # Ends with a valid extension
        if filter_by_extension and not normalize_filename(path).endswith(self.config.valid_file_extensions):
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
                            filename = normalize_filename(path)
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
        if self.config.channel_mode == CHANNEL_MODE_RANDOM:
            random.shuffle(videos)
        elif self.config.channel_mode == CHANNEL_MODE_RANDOM_DETERMINISTIC:
            shuffle_deterministic(videos)
        elif self.config.channel_mode == CHANNEL_MODE_ALPHABETICAL:
            videos.sort(key=channel_sort_key)
        else:
            videos_config = [v for v in videos if v[0]]
            if self.config.channel_mode == CHANNEL_MODE_CONFIG_ONLY:
                videos = videos_config
            else:
                videos_non_config = [v for v in videos if not v[0]]
                if self.config.channel_mode == CHANNEL_MODE_CONFIG_FIRST_RANDOM:
                    random.shuffle(videos_non_config)
                elif self.config.channel_mode == CHANNEL_MODE_CONFIG_FIRST_RANDOM_DETERMINISTIC:
                    shuffle_deterministic(videos_non_config)
                elif self.config.channel_mode == CHANNEL_MODE_CONFIG_FIRST_ALPHABETICAL:
                    videos_non_config.sort(key=channel_sort_key)
                videos = videos_config + videos_non_config

        videos = [Video(videos_db=self, from_config=from_config, **video) for from_config, video in videos]
        # Operation should be atomic, assign both at same time
        with self._channel_lock:
            self._videos = {"objects": videos, "channels": {v.path: i for i, v in enumerate(videos)}}
            if self._websocket_updates_queue is not None:
                self._websocket_updates_queue.put({"type": "videos_db", "data": [v.serialize() for v in self.videos]})
            else:
                logger.critical("No websocket queue! Something went wrong (or using --generate_videos_config).")
            logger.info(f"Generated {len(self.videos)} channels, ignored {ignored_files} files")
            if videos:
                self.has_videos_event.set()
            else:
                self.has_videos_event.clear()
        # Let go of lock, could have good jumbled logs but it's a trace so it doesn't matter
        for path, channel in self.channels.items():
            logger.trace(f"Mapped {path} to channel {channel + 1}")

    @property
    def videos(self) -> list[Video]:
        return self._videos["objects"]

    @property
    def channels(self) -> dict[Path, int]:
        return self._videos["channels"]

    def videos_for_rating(self, min_rating: Literal[False] | str) -> list[Video]:
        if min_rating:
            return [v for v in self.videos if v.is_viewable_based_on_rating(min_rating)]
        else:
            return self.videos

    def get_random_video(self, current_rating: Literal[False] | str = False) -> Video:
        with self._channel_lock:  # Prevents self.videos from being modified while working here
            videos = self.videos_for_rating(current_rating)
            if videos:
                video = random.choice(videos)
                logger.debug(f"Randomly chose video {video.path}")
            else:
                logger.warning(f"No videos found{f' for rating {current_rating}' if current_rating else ''}")
                video = None

        return video

    def get_video_for_channel_change(
        self, video: Video, current_rating: Literal[False] | str = False, direction: int = 1
    ) -> Video:
        with self._channel_lock:  # Prevents self.videos from being modified while working here
            current_channel = max(video.channel, 0)  # In case channel is -1
            num_channels = len(self.videos)
            if num_channels == 0:
                logger.warning(
                    f"No {'next' if direction == 1 else 'previous'} channel"
                    f" found{f' for rating {current_rating}' if current_rating else ''}"
                )
                return None

            for i in range(1, num_channels + 1):
                next_channel_index = (current_channel + direction * i) % num_channels
                next_video = self.videos[next_channel_index]
                if next_video.is_viewable_based_on_rating(current_rating):
                    return next_video
            else:
                logger.warning(
                    f"No {'next' if direction == 1 else 'previous'} channel"
                    f" found{f' for rating {current_rating}' if current_rating else ''}"
                )
                return None

    def get_video_by_path(self, path: str | Path) -> Video:
        path = Path(path)
        with self._channel_lock:
            channel = self.channels.get(path)
            if channel is None:
                return None
            return self.videos[channel]

    def rebuild_channels_thread(self):
        while True:
            self._rebuild_event.wait()
            time.sleep(1)  # Wait a second for udisks2 to mount properly, and debounce
            self._rebuild_event.clear()
            self._rebuild_channels()

    def _watch_thread_helper(self, search_dirs: list[Path], recursive: bool):
        logger.debug(f"Watching search directories ({recursive=}): {', '.join(map(str, search_dirs))}")
        for changes in watchfiles.watch(
            *search_dirs,
            stop_event=self.watch_stop_event,
            # New folders should trigger a rebuild, since that's what happens when a filesystem is mounted
            # Therefore we can't filter by extension
            watch_filter=lambda _, path: self._is_valid_video_path(Path(path), filter_by_extension=False),
            recursive=recursive,
        ):
            logger.info("Detected file change(s). Queuing for channel rebuild.")
            for change, path in changes:
                logger.debug(f"Detected file change ({change.name}): {path}")
            self._rebuild_event.set()

    def watch_dirs_thread(self, recursive: bool):
        search_dirs = self._search_dirs_recursive if recursive else self._search_dirs
        if search_dirs:
            self._watch_thread_helper(search_dirs, recursive)
        else:
            logger.debug(f"No need to start watch-dirs thread for {recursive=}")

    def mark_bad_video(self, video: Video) -> None:
        self._bad_video_paths.add(video.path)
        self._rebuild_event.set()

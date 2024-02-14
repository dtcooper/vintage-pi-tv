import logging
from pathlib import Path
import queue
import threading
import time

from .config import Config
from .constants import DEFAULT_CONFIG_PATHS
from .keyboard import KEYBOARD_AVAILABLE, Keyboard
from .mpv_wrapper import MPV
from .player import Player
from .utils import (
    get_vintage_pi_tv_version,
    init_logger,
    is_docker,
    is_raspberry_pi,
    retry_thread_wrapper,
    set_log_level,
)
from .videos import VideosDB


logger = logging.getLogger(__name__)


class VintagePiTV:
    def init_config(
        self,
        config_file: str | Path | None = None,
        config_wait: int = 0,
        extra_search_dirs: list | tuple = (),
        log_level_override: None | str = None,
    ):
        if config_file is not None:
            config_file_tries = (config_file,)
        elif not is_docker():
            config_file_tries = DEFAULT_CONFIG_PATHS
        else:
            config_file_tries = ()

        config_file_tries = [Path(p).absolute() for p in config_file_tries]
        self.config: Config = None

        for config_file_try in config_file_tries:
            for i in range(config_wait + 1):
                if config_file_try.exists():
                    logger.info(f"Using config file: {config_file_try}")
                    self.config = Config(
                        path=config_file_try, extra_search_dirs=extra_search_dirs, log_level_override=log_level_override
                    )
                    break
                else:
                    if i < config_wait:
                        logger.warning(f"Config file {config_file_try} not found! Sleeping for 1 second.")
                        time.sleep(1)
            if self.config is not None:
                break
        else:
            if config_file_tries:
                logger.warning(f"Using a default config, none found at: {', '.join(map(str, config_file_tries))}")
            else:
                logger.warning("Using a default config as was none specified")
            self.config = Config(path=None, extra_search_dirs=extra_search_dirs, log_level_override=log_level_override)

    def __init__(
        self,
        config_file: str | Path | None = None,
        config_wait: int = 0,
        extra_search_dirs: list | tuple = (),
        log_level_override: None | str = None,
    ):
        init_logger()
        logger.info(f"Starting Vintage Pi TV version: {get_vintage_pi_tv_version()}")

        self.init_config(config_file, config_wait, extra_search_dirs, log_level_override)

        set_log_level(self.config.log_level)
        logger.debug(f"Changed log level to {self.config.log_level}")

        logger.info("Loaded config")
        logger.debug(f"Running in mode: {is_docker()=}, {is_raspberry_pi()=}")

        event_queue: queue.Queue = queue.Queue()
        self.keyboard: Keyboard | None = None
        if self.config.keyboard["enabled"]:
            if KEYBOARD_AVAILABLE:
                logger.info("Enabling keyboard")
                self.keyboard = Keyboard(config=self.config, event_queue=event_queue)
            elif is_docker():
                logger.info("Enabling keyboard in Docker mode")
            else:
                logger.warning("Can't enable keyboard since it's not available on this platform")
                self.config.keyboard["enabled"] = False

        if (not self.config.keyboard["enabled"] or is_docker()) and self.config.ir_remote["enabled"]:
            logger.warning("Can't enable IR remote if keyboard is disabled (or in Docker dev mode)!")
            self.config.ir_remote["enabled"] = False

        self.mpv: MPV = MPV(config=self.config, event_queue=event_queue)
        self.videos: VideosDB = VideosDB(config=self.config)
        self.player: Player = Player(
            config=self.config, videos_db=self.videos, mpv=self.mpv, keyboard=self.keyboard, event_queue=event_queue
        )

        self.mpv.done_loading()
        logger.debug("Done initializing objects")

    def startup(self):
        threads = [
            (self.videos.watch_thread, {"name": "watch", "kwargs": {"recursive": False}, "daemon": False}),
            (self.videos.watch_thread, {"name": "watch_recursive", "kwargs": {"recursive": True}, "daemon": False}),
            self.videos.rebuild_channels_thread,
            self.player.osd.osd_thread,
            self.player.static.static_thread,
            self.player.player_thread,
        ]
        if self.keyboard:
            threads.append(self.keyboard.keyboard_thread)

        for thread in threads:
            target, kwargs = thread if isinstance(thread, tuple) else (thread, {})
            daemon = kwargs.pop("daemon", True)
            name = kwargs.pop("name", target.__name__.removesuffix("_thread"))
            target = retry_thread_wrapper(target)
            logger.info(f"Spawning {name} thread")
            thread = threading.Thread(target=target, name=name, daemon=daemon, **kwargs)
            thread.start()

        threads = list(threading.enumerate())
        logger.debug(f"{len(threads)} threads are running {', '.join(t.name for t in threads)}")

        logger.info("Loading complete!")

    def shutdown(self):
        # Using a threading.Event for watchfiles prevents weird "FATAL: exception not rethrown" log messages
        self.videos.watch_stop_event.set()

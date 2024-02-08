import logging
from pathlib import Path
import queue
import threading
import time

from .config import Config
from .constants import DEFAULT_CONFIG_PATHS
from .keyboard import KEYBOARD_AVAILABLE, Keyboard
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
        self, config_file: str | Path | None = None, config_wait: int = 0, extra_search_dirs: list | tuple = ()
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
                    self.config = Config(path=config_file_try, extra_search_dirs=extra_search_dirs)
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
            self.config = Config(path=None, extra_search_dirs=extra_search_dirs)

    def __init__(
        self,
        config_file: str | Path | None = None,
        config_wait: int = 0,
        extra_search_dirs: list | tuple = (),
        uvicorn_reload_parent_pid: int | None = None,
    ):
        init_logger()
        logger.info(f"Starting Vintage Pi TV version: {get_vintage_pi_tv_version()}")

        self.init_config(config_file, config_wait, extra_search_dirs)

        set_log_level(self.config.log_level)
        logger.debug(f"Changed log level to {self.config.log_level}")

        logger.info("Loaded config")
        logger.debug(f"Running in mode: {is_docker()=}, {is_raspberry_pi()=}")

        self.event_queue = queue.Queue()
        self.keyboard: Keyboard | None = None
        if KEYBOARD_AVAILABLE:
            if self.config.keyboard["enabled"]:
                self.keyboard = Keyboard(config=self.config, queue=self.event_queue)
        elif self.config.keyboard["enabled"]:
            logger.warning("Can't enable keyboard since it's not available on this platform")
            self.config.keyboard["enabled"] = False

        if not self.config.keyboard["enabled"] and self.config.ir_remote["enabled"]:
            logger.warning("Can't enable IR remote if keyboard is disabled!")
            self.config.ir_remote["enabled"] = False

        self.videos: VideosDB = VideosDB(config=self.config)
        self.player: Player = Player(
            config=self.config, videos_db=self.videos, queue=self.event_queue, reload_pid=uvicorn_reload_parent_pid
        )

    def test_event_queue_consumer_thread(self):
        while item := self.event_queue.get():
            logger.info(f"XXX --- Got keypress: {item}")

    def startup(self):
        threads = [
            {"target": self.player.player_thread},
            {"target": self.player.osd_thread},
            {"name": "watch", "target": self.videos.watch_thread, "kwargs": {"recursive": False}, "daemon": False},
            {
                "name": "watch_recursive",
                "target": self.videos.watch_thread,
                "kwargs": {"recursive": True},
                "daemon": False,
            },
            {"target": self.videos.rebuild_channels_thread},
            {"name": "test", "target": self.test_event_queue_consumer_thread},
        ]
        if self.keyboard:
            threads.append({"name": "keyboard", "target": self.keyboard.keyboard_thread})
        if self.config.static_time > 0:
            threads.append({"name": "static", "target": self.player.run_static_thread})

        for kwargs in threads:
            kwargs.setdefault("daemon", True)
            kwargs.setdefault("name", kwargs["target"].__name__.removesuffix("_thread"))
            kwargs["target"] = retry_thread_wrapper(kwargs["target"])
            logger.info(f"Spawning {kwargs['name']} thread")
            thread = threading.Thread(**kwargs)
            thread.start()

        threads = list(threading.enumerate())
        logger.debug(f"{len(threads)} threads are running {', '.join(t.name for t in threads)}")

        for level in ("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "TRACE"):
            logger.log(getattr(logging, level), f"Test {level} message")

    def shutdown(self):
        # Using a threading.Event for watchfiles prevents weird "FATAL: exception not rethrown" log messages
        self.videos.watch_stop_event.set()

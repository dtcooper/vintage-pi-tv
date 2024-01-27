import asyncio
import logging
from pathlib import Path
import sys
import time
from typing import Literal

from .config import Config
from .constants import DEFAULT_CONFIG_PATHS
from .player import Player
from .utils import init_logger, set_log_level
from .videos import VideosDB


logger = logging.getLogger(__name__)


class VintagePiTV:
    def init_config_from_file(
        self,
        config_file: str | Path | None = None,
        config_wait: int = 0,
        extra_search_dirs: list | tuple = (),
        dev_mode: Literal["docker"] | bool = False,
    ):
        config_file_tries = DEFAULT_CONFIG_PATHS if config_file is None else (config_file,)
        config_file_tries = [Path(p).absolute() for p in config_file_tries]
        self.config = None

        for config_file_try in config_file_tries:
            for i in range(config_wait + 1):
                if config_file_try.exists():
                    self.config = Config(path=config_file_try, extra_search_dirs=extra_search_dirs, dev_mode=dev_mode)
                    break
                else:
                    if i < config_wait:
                        logger.warning(f"Config file {config_file_try} not found! Sleeping for 1 second.")
                        time.sleep(1)
            if self.config is not None:
                break
        else:
            logger.critical(f"Exiting as config file not found at path(s): {', '.join(map(str, config_file_tries))}")
            sys.exit(1)

    def init_config_with_no_file(
        self, extra_search_dirs: list | tuple = (), dev_mode: Literal["docker"] | bool = False
    ):
        self.config = Config(path=None, extra_search_dirs=extra_search_dirs, dev_mode=dev_mode)

    def __init__(
        self,
        config_file: str | Path | None = None,
        config_wait: int = 0,
        dev_mode: Literal["docker"] | bool = False,
        extra_search_dirs: list | tuple = (),
        no_config: bool = False,
        uvicorn_reload_parent_pid: int | None = None,
    ):
        init_logger()

        # No config is explicit OR we're running in docker
        if no_config or (config_file is None and isinstance(dev_mode, str) and dev_mode == "docker"):
            self.init_config_with_no_file(extra_search_dirs, dev_mode=dev_mode)
        else:
            self.init_config_from_file(
                config_file=config_file, config_wait=config_wait, extra_search_dirs=extra_search_dirs, dev_mode=dev_mode
            )

        set_log_level(self.config.log_level)
        logger.info(f"Loaded config: {config_file}")
        logger.debug(f"Initialized log level {self.config.log_level}")

        self.videos = VideosDB(config=self.config)
        self.player = Player(config=self.config, videos_db=self.videos, reload_pid=uvicorn_reload_parent_pid)

    def startup(self):
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, self.player.run)

    async def shutdown(self):
        self.player.stop()

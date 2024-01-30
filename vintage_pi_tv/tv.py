import asyncio
import logging
from pathlib import Path
import time

from .config import Config
from .constants import DEFAULT_CONFIG_PATHS
from .player import Player
from .utils import get_vintage_pi_tv_version, init_logger, is_docker, is_raspberry_pi, set_log_level
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
        self.config = None

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

        self.videos = VideosDB(config=self.config)
        self.player = Player(config=self.config, videos_db=self.videos, reload_pid=uvicorn_reload_parent_pid)

    def startup(self):
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, self.player.run)

    async def shutdown(self):
        self.player.stop()

import asyncio
import logging
from pathlib import Path
import sys
import time

from .config import Config
from .constants import DEFAULT_CONFIG_PATHS
from .player import Player
from .utils import init_logger, set_log_level
from .videos import VideosDB


logger = logging.getLogger(__name__)


class VintagePiTV:
    def __init__(self, config_file=None, wait_for_config_seconds=0):
        init_logger()

        config_file_tries = DEFAULT_CONFIG_PATHS if config_file is None else (config_file,)
        self.config = None

        for config_file_try in config_file_tries:
            path = Path(config_file_try)
            for i in range(wait_for_config_seconds + 1):
                if path.exists():
                    self.config = Config(path)
                    break
                else:
                    if i < wait_for_config_seconds:
                        logger.warning(f"Config file {config_file_try} not found! Sleeping for 1 second.")
                        time.sleep(1)
            if self.config is not None:
                break
        else:
            logger.critical(f"Exiting as config file not found at path(s): {', '.join(config_file_tries)}")
            sys.exit(1)

        set_log_level(self.config.log_level)
        logger.info(f"Loaded config: {config_file}")
        logger.debug(f"Initialized log level {self.config.log_level}")

        self.videos = VideosDB(config=self.config)
        self.player = Player(config=self.config, videos_db=self.videos)

    def startup(self):
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, self.player.run)

    async def shutdown(self):
        self.player.stop()

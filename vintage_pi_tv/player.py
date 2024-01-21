import logging
import sys
import time

import mpv


logger = logging.getLogger(__name__)


class Player:
    def __init__(self, config, videos_db):
        self.config = config
        self.videos_db = videos_db
        self.should_exit = False

        try:
            self.mpv = mpv.MPV(force_window="immediate", ao=self.config.audio_driver)
        except Exception:
            logger.exception("Error initializing mpv. Are you sure 'extra_mpv_options' are configured properly?")
            sys.exit(1)

    def stop(self):
        self.should_exit = True

    def run(self):
        while not self.should_exit:
            video = self.videos_db.get_next_video()
            logger.debug(f"run({video!r})")
            time.sleep(1)
        logger.info("Player thread exiting.")

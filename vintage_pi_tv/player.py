import logging
from pathlib import Path
import sys
import time

import mpv

from .config import Config
from .videos import Video, VideosDB


logger = logging.getLogger(__name__)


class Player:
    def __init__(self, config: Config, videos_db: VideosDB):
        self.config = config
        self.videos_db = videos_db
        self.should_exit = False

        # Prep arguents for MPV
        kwargs = {"force_window": "immediate", "ao": self.config.audio_driver}
        if self.config.enable_audio_visualization:
            kwargs.update({
                "scripts": str(Path(__file__).parent / "visualizer.lua"),
                "script_opts": "visualizer-name=avectorscope,visualizer-height=12",
            })

        logger.debug(f"Executing MPV with arguments: {kwargs}")
        try:
            self.mpv = mpv.MPV(**kwargs)
        except Exception:
            logger.exception("Error initializing mpv. Are you sure 'extra_mpv_options' are configured properly?")
            sys.exit(1)

        self.width: int
        self.height: int
        self.width, self.height = self.mpv.osd_width, self.mpv.osd_height

        self.playing = False
        self.duration = 0

        @self.mpv.event_callback("end-file")
        def callback(*args, **kwargs):
            self.playing = False

        def observe(name, value):
            pass

        for prop in ("time-pos/full", "duration/full", "idle-active", "osd-dimensions"):
            self.mpv.observe_property(prop, observe)

    def stop(self):
        self.should_exit = True

    def play(self, video: Video):
        self.playing = True
        self.mpv.loadfile(str(video.path))

    # def loop(self):
    #     while not self.should_exit:
    #         self.play(self.videos_db.get_next_video())

    def run(self):
        self.play(self.videos_db.get_next_video())

        # Wait for file to play
        while not self.should_exit and self.mpv.core_idle and self.playing:
            time.sleep(0.05)

        if self.playing:
            self.mpv.seek(1000)

        import ipdb; ipdb.set_trace()

        while not self.should_exit:
            # print(f'loop tid: {threading.current_thread().ident}')
            # logger.debug(f"run({video!r})")
            time.sleep(0.05)
        logger.info("Player thread exiting.")

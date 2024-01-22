from functools import partial
import logging
import os
from pathlib import Path
import random
import signal
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
        kwargs = {
            "force_window": "immediate",
            "ao": self.config.audio_driver,
            "vo": self.config.video_driver,
            "profile": "sw-fast",
        }
        if self.config.enable_audio_visualization:
            kwargs.update({
                "scripts": str(Path(__file__).parent / "visualizer.lua"),
                "script_opts": "visualizer-name=avectorscope,visualizer-height=12",
            })

        if self.config.video_driver == "drm":
            kwargs.update({
                "profile": "sw-fast",
            })

        kwargs.update(**self.config.extra_mpv_options)
        for key, value in self.config.extra_mpv_options.items():
            if not value:
                del kwargs[key]

        logger.debug(f"Initializing MPV with arguments: {kwargs}")
        try:
            self.mpv = mpv.MPV(log_handler=partial(print, end=""), **kwargs)
        except Exception as e:
            # Excepts from mpv library formed weirdlty
            if (
                len(e.args) == 3
                and isinstance(e.args[2], tuple)
                and len(e.args[2]) == 3
                and isinstance(e.args[2][1], bytes)
                and isinstance(e.args[2][2], bytes)
            ):
                logger.critical(
                    f"Can't initialize mpv: Invalid option: {e.args[2][1].decode()} = {e.args[2][2].decode()!r}!"
                    " Exiting"
                )
            else:
                logger.exception("Error initializing mpv. Are you sure 'extra_mpv_options' are configured properly?")
            sys.exit(1)

        self.width: int
        self.height: int
        self.width, self.height = self.mpv.osd_width, self.mpv.osd_height

        self.playing = False
        self.duration = 0

        @self.mpv.event_callback("end-file")
        def _(*args, **kwargs):
            self.playing = False

        def observe(name, value):
            logger.debug(f"VALUE CHANGE: {name} = {value!r}")

        for prop in ("time-pos/full", "duration/full", "idle-active", "osd-dimensions", "core-idle"):
            self.mpv.observe_property(prop, observe)

        @self.mpv.event_callback("shutdown")
        def _(*args, **kwargs):
            # Seems to happen when you click "X" on the X11 video driver
            pid = int(os.environ.get("VINTAGE_PI_TV_UVICORN_RELOAD_PARENT_PID") or os.getpid())
            logger.critical(f"mpv appears to have been shut down! Forcing exit of program (pid: {pid})")
            os.kill(pid, signal.SIGINT)

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
            self.mpv.seek(random.uniform(0.0, self.mpv.duration))

        while not self.should_exit:
            # print(f'loop tid: {threading.current_thread().ident}')
            # logger.debug(f"run({video!r})")
            time.sleep(0.05)
        logger.info("Player thread exiting.")

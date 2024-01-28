import logging
import os
from pathlib import Path
import random
import signal
import string
import sys
import time

import mpv
import numpy

from .config import Config
from .utils import FPSClock
from .videos import Video, VideosDB


logger = logging.getLogger(__name__)
mpv_log_level_mapping = {
    "fatal": logging.CRITICAL,
    "error": logging.ERROR,
    "warn": logging.WARNING,
    "info": logging.INFO,
    "status": logging.INFO,
    "v": logging.DEBUG,
    "debug": logging.DEBUG,
}


def mpv_log(level, prefix, text):
    logger.log(mpv_log_level_mapping.get(level, logging.INFO), f"[mpv/{prefix}] {text.rstrip()}")


class Player:
    def __init__(self, config: Config, videos_db: VideosDB, reload_pid: int | None = None):
        self.config = config
        self.videos_db = videos_db
        self.reload_pid = reload_pid
        self.should_exit = False

        # Prep arguents for MPV
        kwargs = {k.replace("-", "_"): v for k, v in self.config.mpv_options.items() if not isinstance(v, bool) or v}
        if self.config.enable_audio_visualization:
            kwargs.update({
                "scripts": str(Path(__file__).parent / "visualizer.lua"),
                "script_opts": "visualizer-name=avectorscope,visualizer-height=12",
            })

        logger.debug(f"Initializing MPV with arguments: {kwargs}")
        try:
            self.mpv = mpv.MPV(log_handler=mpv_log, loglevel="status", force_window="immediate", **kwargs)
        except Exception as e:
            # Exceptions from mpv are formed very weirdly
            if (
                len(e.args) == 3
                and isinstance(e.args[2], tuple)
                and len(e.args[2]) == 3
                and isinstance(e.args[2][1], bytes)
                and isinstance(e.args[2][2], bytes)
            ):
                logger.critical(f"Invalid mpv option: {e.args[2][1].decode()} = {e.args[2][2].decode()!r}! Exiting.")
            else:
                logger.critical(
                    "Error initializing mpv. Are you sure 'mpv_options' are set properly? Exiting.", exc_info=True
                )
            sys.exit(1)

        # Since we're primarily operating in fullscreen mode, window size should not be changed
        # And if it does change, user is shit out of luck
        self.width, self.height = self.mpv.osd_width, self.mpv.osd_height
        logger.info(f"Dimensions {self.width}x{self.height}")

        self.playing = False
        self.killed = False
        self.duration = 0

        @self.mpv.event_callback("end-file")
        def _(*args, **kwargs):
            logger.debug(f"end-file: {args=}, {kwargs=}")
            self.playing = False

        def observe(name, value):
            logger.debug(f"VALUE CHANGE: {name} = {value!r}")

        # for prop in ("time-pos/full", "duration/full", "idle-active", "osd-dimensions", "core-idle"):
        #     self.mpv.observe_property(prop, observe)

        @self.mpv.event_callback("shutdown")
        def _(*args, **kwargs):
            logger.debug(f"shutdown: {args=}, {kwargs=}")
            # Seems to happen when you click "X" on the X11 video driver
            self.kill_entire_app()

        @self.mpv.key_binding("ESC")
        def _(state, name, char):
            logger.debug(f"ESC: {state=}, {name=}, {char=}")
            self.kill_entire_app()

        @self.mpv.key_binding("MBTN_LEFT")
        def _(state, name, char):
            if state[0] == "d":
                logger.debug(f"Left click, osd dimensions: {self.mpv.osd_width}x{self.mpv.osd_height}")

        def keydown(state, name, char):
            logger.debug(f"KEYPRESS: {state=}, {name=}, {char=}")

        for k in string.ascii_lowercase:
            self.mpv.register_key_binding(k, keydown)

    def stop(self):
        self.should_exit = True

    def play(self, video: Video):
        self.playing = True
        self.mpv.loadfile(str(video.path))

    def kill_entire_app(self):
        if not self.killed:
            pid = self.reload_pid or os.getpid()
            logger.critical(f"mpv appears to have been shut down! Forcing exit of program (pid: {pid})")
            self.killed = True
            os.kill(pid, signal.SIGINT)

    # def loop(self):
    #     while not self.should_exit:
    #         self.play(self.videos_db.get_next_video())

    def get_static_frame(self):
        width, height = self.mpv.osd_width, self.mpv.osd_height
        frame = numpy.random.randint(0, 0xFF + 1, width * height * 4, dtype=numpy.uint8)
        frame[3::4] = 0xFF
        return width, height, frame

    def show_static(self):
        start = time.monotonic()
        clock = FPSClock()

        frames = [self.get_static_frame() for _ in range(16)]
        i = 0

        while time.monotonic() - 3.5 < start:
            width, height, static_frame = frames[i]
            i = (i + 1) % len(frames)
            if i == 0:
                random.shuffle(frames)

            source = f"&{static_frame.ctypes.data}"
            self.mpv.overlay_add(1, 0, 0, source, 0, "bgra", width, height, width * 4)
            clock.tick(60)
        self.mpv.overlay_remove(1)

    def run(self):
        self.show_static()

        self.play(self.videos_db.get_next_video())
        # self.play(self.videos_db.videos[Path("/home/dave/media/DTC/videos/until-the-end-of-the-world.mkv")])

        # Wait for file to play
        while not self.should_exit and self.mpv.core_idle and self.playing:
            time.sleep(0.05)

        if self.playing:
            self.mpv.seek(random.uniform(0.0, self.mpv.duration))

        i = 0
        logger.debug(self.mpv.video_params)

        while not self.should_exit:
            # print(f'loop tid: {threading.current_thread().ident}')
            # logger.debug(f"run({video!r})")
            time.sleep(0.05)
            i += 1
            if i > 2500:
                self.kill_entire_app()

        logger.info("Player thread exiting.")

import logging
import os
from pathlib import Path
import queue
import random
import signal
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
    def __init__(self, config: Config, videos_db: VideosDB, queue: queue.Queue, reload_pid: int | None = None):
        self.config = config
        self.videos_db = videos_db
        self.queue = queue
        self.reload_pid = reload_pid
        self.should_exit = False
        self._static_frames: list | None = None
        self._static_height: int
        self._static_width: int
        self._last_static_frame_indexes: list = []

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
            if (
                len(e.args) == 3
                and e.args[1] == mpv.ErrorCode.OPTION_NOT_FOUND
                and len(e.args[2]) == 3
                and isinstance(e.args[2][1], bytes)
                and isinstance(e.args[2][2], bytes)
            ):
                logger.critical(
                    f"Invalid mpv option: {e.args[2][1].decode()} = {e.args[2][2].decode()!r}! Exiting.", exc_info=True
                )
            else:
                logger.critical(
                    "Error initializing mpv. Are you sure 'mpv_options' are set properly? Exiting.", exc_info=True
                )
            sys.exit(1)
        logger.info("MPV initialized")

        # Since we're primarily operating in fullscreen mode, window size should not be changed
        # And if it does change, user is shit out of luck
        self.width, self.height = self.mpv.osd_width, self.mpv.osd_height
        logger.info(f"Screen dimensions {self.width}x{self.height}")

        self.playing = False
        self.killed = False
        self.duration = 0

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
        """Generate random static frame from a cache of 15 frames, with no repetitions for up to 5 frames"""
        if not self._static_frames:
            self._static_frames = []
            self._static_width, self._static_height = self.mpv.osd_width, self.mpv.osd_height
            size = self._static_width * self._static_height * 4
            logger.debug("Generating 15 static frames")
            for _ in range(15):
                frame = numpy.random.randint(0, 0xFF + 1, size, dtype=numpy.uint8)
                frame[3::4] = 0xFF
                self._static_frames.append(frame)
            logger.debug("Done generating frames")

        choices = list(set(range(len(self._static_frames))) ^ set(self._last_static_frame_indexes))
        frame_index = random.choice(choices)
        frame = self._static_frames[frame_index]
        self._last_static_frame_indexes.append(frame_index)
        if len(self._last_static_frame_indexes) > 5:
            self._last_static_frame_indexes.pop(0)

        return self._static_width, self._static_height, frame

    def show_static(self):
        start = time.monotonic()
        clock = FPSClock()

        while time.monotonic() - 2 < start:
            width, height, static_frame = self.get_static_frame()

            source = f"&{static_frame.ctypes.data}"
            self.mpv.overlay_add(1, 0, 0, source, 0, "bgra", width, height, width * 4)
            clock.tick(60)
        self.mpv.overlay_remove(1)

    def run_thread(self):
        self.show_static()
        video = self.videos_db.get_next_video()

        if video is None:
            self.critical("No videos. Exiting.")
            self.kill_entire_app()
        else:
            logger.info(f"Playing {video.path}")
            self.play(video)
        # self.play(self.videos_db.videos[Path("/home/dave/media/DTC/videos/until-the-end-of-the-world.mkv")])

        # Wait for file to play
        while not self.should_exit and self.mpv.core_idle and self.playing:
            time.sleep(0.05)

        if self.playing:
            self.mpv.seek(random.uniform(0.0, self.mpv.duration))

        i = 0

        while not self.should_exit:
            time.sleep(0.05)
            i += 1
            if i > 2500:
                self.kill_entire_app()

        logger.info("Player thread exiting.")

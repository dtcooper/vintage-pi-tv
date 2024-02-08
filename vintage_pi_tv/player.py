import logging
import os
from pathlib import Path
import queue
import random
import signal
import sys
import threading
from time import monotonic

import mpv
import numpy
import numpy.typing
import pygame
import pygame.freetype

from .config import Config
from .utils import FPSClock
from .videos import Video, VideosDB


pygame.freetype.init()


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
        self._static_event: threading.Event = threading.Event()
        self._status_event: threading.Event = threading.Event()
        self._config = config
        self._videos_db = videos_db
        self.queue = queue
        self._reload_pid = reload_pid

        # Prep arguents for MPV
        kwargs = {k.replace("-", "_"): v for k, v in self._config.mpv_options.items() if not isinstance(v, bool) or v}
        if self._config.enable_audio_visualization:
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

        # Since we're primarily operating in fullscreen mode (except in development) window size should not be changed.
        # And if it does change, user is shit out of luck
        self.width: int = self.mpv.osd_width
        self.height: int = self.mpv.osd_height
        self.size: tuple[int, int] = (self.width, self.height)
        self.shape: tuple[int, int, int] = (self.width, self.height, 4)
        self.status_overlay_array: numpy.typing.ArrayLike = numpy.zeros(self.shape, dtype=numpy.uint8)
        self.status_overlay: pygame.Surface = pygame.image.frombuffer(self.status_overlay_array, self.size, "BGRA")
        self.menu_overlay_array: numpy.typing.ArrayLike = numpy.zeros(self.shape, dtype=numpy.uint8)
        self.menu_overlay: pygame.Surface = pygame.image.frombuffer(self.status_overlay_array, self.size, "BGRA")
        self.font_cache: dict[int, pygame.font.Font] = {}
        self.font_size_scale: float = min(self.width * 9 / 16, self.height) / 720
        self.font: pygame.freetype.Font = pygame.freetype.Font(Path(__file__).parent / "undefined-medium.ttf")

    def render_text(self, text, color, size):
        return self.font.render(text, color, size=size * self.font_size_scale)

    def kill_entire_app(self):
        if not self.killed:
            pid = self._reload_pid or os.getpid()
            logger.critical(f"mpv appears to have been shut down! Forcing exit of program (pid: {pid})")
            self.killed = True
            os.kill(pid, signal.SIGINT)

    def update_overlay(self, overlay, num):
        self.mpv.overlay_add(num, 0, 0, f"&{overlay.ctypes.data}", 0, "bgra", self.width, self.height, self.width * 4)

    def remove_overlay(self, num):
        self.mpv.overlay_remove(num)

    def run_static_thread(self):
        frames = []
        for _ in range(15):
            frame = numpy.random.randint(0, 0xFF + 1, self.shape, dtype=numpy.uint8)
            frame[:, :, -1] = 0xFF
            frames.append(frame)
        logger.debug(f"{len(frames)} static frames ({self.width}x{self.height}) were pre-rendered")

        no_repeat_num = len(frames) // 3
        indexes = set(range(len(frames)))
        clock = FPSClock()

        while True:
            self._static_event.wait()
            last_indexes = []

            while self._static_event.is_set():
                no_repeat_indexes = list(indexes ^ set(last_indexes))
                index = random.choice(no_repeat_indexes)
                frame = frames[index]

                self.update_overlay(frame, num=0)

                last_indexes.append(index)
                if len(last_indexes) > no_repeat_num:
                    last_indexes.pop(0)
                clock.tick(24)
            self.remove_overlay(0)

    def run_osd_thread(self):
        pass

    def run_player_thread(self):
        self._static_event.set()
        end_static = monotonic() + self._config.static_time
        end_status = -1
        clock = FPSClock()
        video: Video | None = None

        text = self.render_text("Hi, mom!", "blue", 64)
        self.status_overlay.blit(text[0], (0, 0))
        self.update_overlay(self.status_overlay_array, 5)

        while True:
            now = monotonic()

            if now > end_static:
                self._static_event.clear()
                if video is None:
                    pass

            if now > end_status:
                self._status_event.clear()

            clock.tick(12)

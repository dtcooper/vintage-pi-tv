import datetime
import logging
import os
from pathlib import Path
import queue
import random
import signal
import sys
import threading
from time import monotonic as tick

import mpv
import numpy
import numpy.typing
import pygame
from pygame import freetype
from pygame.freetype import STYLE_DEFAULT, STYLE_OBLIQUE

from .config import Config
from .constants import BLACK, TRANSPARENT, WHITE
from .utils import FPSClock
from .videos import Video, VideosDB


freetype.init()


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

        if self._config.aspect_mode == "zoom":
            logger.debug("Setting panscan to 1.0 for zoom")
            kwargs["panscan"] = "1.0"

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

        # Since we're primarily operating in fullscreen mode (except in development) window size should not be changed.
        # And if it does change, user is shit out of luck
        width: int = self.mpv.osd_width
        height: int = self.mpv.osd_height

        margins = self._config.overscan_margins
        for margin, dimension in (("left", width), ("top", height), ("right", width), ("bottom", height)):
            if (pixels := margins[margin]) > 0:
                amount = pixels / dimension
                logger.debug(f"Set {margin} margin to {amount:0.5f} ({pixels}px)")
                setattr(self.mpv, f"video_margin_ratio_{margin}", amount)

        self.margin_left = margins["left"]
        self.margin_top = margins["top"]
        self.width: int = max(width - margins["left"] - margins["right"], 1)
        self.height: int = max(height - margins["top"] - margins["bottom"], 1)
        if self._config.aspect_mode == "stretch":
            aspect = self.width / self.height
            logger.debug(f"Set aspect ratio to {aspect} for stretch")
            self.mpv.video_aspect_override = str(aspect)

        logger.info(f"MPV initialized (screen: {width}x{height}, with margins: {self.width}x{self.height})")

        self.size: tuple[int, int] = (self.width, self.height)
        self.shape: tuple[int, int, int] = (self.width, self.height, 4)
        self.status_overlay_array: numpy.typing.ArrayLike = numpy.zeros(self.shape, dtype=numpy.uint8)
        self.status_overlay: pygame.Surface = pygame.image.frombuffer(self.status_overlay_array, self.size, "BGRA")
        self.menu_overlay_array: numpy.typing.ArrayLike = numpy.zeros(self.shape, dtype=numpy.uint8)
        self.menu_overlay: pygame.Surface = pygame.image.frombuffer(self.status_overlay_array, self.size, "BGRA")
        self.font_cache: dict[int, pygame.font.Font] = {}
        self.font_scale: float = min(self.width * 9 / 16, self.height) / 720
        self.pixel_scale: float = min(self.width * 9 / 16, self.height) / 360
        self.font: freetype.Font = freetype.Font(Path(__file__).parent / "undefined-medium.ttf")

        self._generate_no_videos_overlay()

    def _generate_no_videos_overlay(self):
        self._no_videos_overlay_shown: bool = False
        self._no_videos_overlay_array: numpy.typing.ArrayLike = numpy.zeros(self.shape, dtype=numpy.uint8)
        no_videos_overlay = pygame.image.frombuffer(self._no_videos_overlay_array, self.size, "BGRA")
        no_videos_overlay.fill(BLACK)
        top, top_rect = self.render_text("No video files detected!", 58)
        bottom, bottom_rect = self.render_text("Waiting. Please insert USB drive with videos.", 34, style=STYLE_OBLIQUE)
        surf = pygame.Surface(
            (max(top_rect.width, bottom_rect.width), top_rect.height + bottom_rect.height + self.pixel_scale * 20),
        )
        rect = surf.get_rect()
        surf.blit(top, top.get_rect(top=0, centerx=rect.centerx))
        surf.blit(bottom, bottom.get_rect(bottom=rect.bottom, centerx=rect.centerx))
        no_videos_overlay.blit(surf, surf.get_rect(center=no_videos_overlay.get_rect().center))

    def render_text(
        self, text, size, color=WHITE, bgcolor=TRANSPARENT, style=STYLE_DEFAULT
    ) -> tuple[pygame.Surface, pygame.Rect]:
        return self.font.render(text, fgcolor=color, bgcolor=bgcolor, size=size * self.font_scale, style=style)

    def kill_entire_app(self):
        if not self.killed:
            pid = self._reload_pid or os.getpid()
            logger.critical(f"mpv appears to have been shut down! Forcing exit of program (pid: {pid})")
            self.killed = True
            os.kill(pid, signal.SIGINT)

    def update_overlay(self, overlay, num):
        self.mpv.overlay_add(
            num,
            self.margin_left,
            self.margin_top,
            f"&{overlay.ctypes.data}",
            0,
            "bgra",
            self.width,
            self.height,
            self.width * 4,
        )

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

    def osd_thread(self):
        pass

    def _no_videos_overlay(self, show: bool = True):
        # Highest possible overlay
        if show and not self._no_videos_overlay_shown:
            self.update_overlay(self._no_videos_overlay_array, 63)
            self._no_videos_overlay_shown = True
        elif not show and self._no_videos_overlay_shown:
            self.remove_overlay(63)
            self._no_videos_overlay_shown = False

    def player_thread(self):
        self._static_event.set()
        end_static = tick() + self._config.static_time
        end_osd = -1
        clock = FPSClock()
        video: Video | None = None

        while True:
            now = tick()

            if now > end_static:
                if video is None:
                    video = self._videos_db.get_random_video()
                    if video is None:
                        self._static_event.clear()
                    else:
                        # video = self._videos_db.get_random_video()
                        self._static_event.set()
                        self.mpv.loadfile(str(video.path))
                        try:
                            self.mpv.wait_until_playing(timeout=10)
                        except TimeoutError:
                            self._static_event.clear()
                            logger.warning(f"Video {video} didn't work! Disabling it.")
                        else:
                            self._static_event.clear()
                            duration = self.mpv.duration
                            place = random.uniform(0, self.mpv.duration)
                            logger.debug(
                                f"Playing {video.path} and Seeking to {datetime.timedelta(seconds=place)} /"
                                f" {datetime.timedelta(seconds=duration)}"
                            )
                            self.mpv.seek(place)

                self._no_videos_overlay(show=video is None)
            else:
                self._no_videos_overlay(show=False)

            if now > end_osd:
                self._status_event.clear()

            clock.tick(12)

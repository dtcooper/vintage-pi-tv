import datetime
import enum
import logging
import random
import threading
from time import monotonic as tick

import numpy
import numpy.typing
from pygame import freetype

from .config import Config
from .constants import BLACK, NO_FILES_LAYER, STATIC_LAYER
from .mpv_wrapper import MPV, Overlay
from .utils import FPSClock
from .videos import Video, VideosDB


logger = logging.getLogger(__name__)


class PlayerState(enum.IntEnum):
    STATIC = 1
    NEEDS_FILES = 2
    PLAYING = 3


class Static:
    NUM_OVERLAYS = 12
    NUM_NO_REPEATS = 6

    def __init__(self, mpv: MPV):
        self._event: threading.Event = threading.Event()
        # self._event.set()
        self._overlays: list[Overlay] = []
        for _ in range(self.NUM_OVERLAYS):
            array = numpy.random.randint(0, 0xFF + 1, mpv.shape, dtype=numpy.uint8)
            array[:, :, -1] = 0xFF
            overlay = mpv.create_overlay(STATIC_LAYER, array, add_pygame_surface=False)
            self._overlays.append(overlay)

    def static_thread(self):
        indexes = set(range(self.NUM_OVERLAYS))
        clock = FPSClock()

        while True:
            self._event.wait()
            last_indexes: int = []

            while self._event.is_set():
                no_repeat_indexes = list(indexes ^ set(last_indexes))
                index = random.choice(no_repeat_indexes)
                self._overlays[index].update()

                last_indexes.append(index)
                if len(last_indexes) > self.NUM_NO_REPEATS:
                    last_indexes.pop(0)

                clock.tick(random.randint(20, 30))
                print(datetime.datetime.now())

            self._overlays[0].clear()  # Clear any of them, since they're all num = 62

    def start(self):
        self._event.set()

    def stop(self):
        self._event.clear()


class Player:
    def __init__(self, config: Config, videos_db: VideosDB, mpv: MPV):
        self.mpv = mpv
        self.static = Static(mpv=mpv)
        self._generate_no_videos_overlay()
        self.state = PlayerState.STATIC

    def _generate_no_videos_overlay(self):
        overlay = self.mpv.create_overlay(NO_FILES_LAYER)
        text, rect = self.mpv.render_multiple_lines(
            (
                {"text": "No video files detected!", "size": 58},
                {"text": "Waiting. Please insert USB drive with videos.", "size": 36, "style": freetype.STYLE_OBLIQUE},
            ),
            bgcolor=BLACK,
            padding=10,
            padding_between=25,
        )
        overlay.surf.fill(BLACK)
        rect.center = overlay.rect.center
        overlay.surf.blit(text, rect)
        self._no_videos_overlay = overlay
        overlay.update()

        # timer = threading.Timer(2, overlay.clear)
        # timer.start()

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
        clock = FPSClock()
        video: Video | None = None

        while True:
            if tick() > end_static:
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
                            place = self.mpv.duration - 30.0  # random.uniform(0, self.mpv.duration)
                            logger.debug(
                                f"Playing {video.path} and Seeking to {datetime.timedelta(seconds=place)} /"
                                f" {datetime.timedelta(seconds=duration)}"
                            )
                            self.mpv.seek(place, "relative")

                    self._no_videos_overlay(show=video is None)
                else:
                    if self.mpv.idle_active:
                        logger.debug(f"Playback for {video.path} done!")
                        video = None
                        self._static_event.set()
                        end_static = tick() + self._config.static_time

            else:
                self._no_videos_overlay(show=False)

            clock.tick(12)

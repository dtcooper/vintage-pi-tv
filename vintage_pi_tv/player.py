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


class PlayerState(enum.StrEnum):
    STATIC = "static"
    NEEDS_FILES = "needs-files"
    PLAYING = "playing"


class PlayState(enum.StrEnum):
    NOT_PLAYING = "not-playing"
    LOADING = "loading"
    PLAYING = "playing"
    PAUSED = "paused"


class Static:
    NUM_OVERLAYS = 15
    NUM_NO_REPEATS = 7

    def __init__(self, config: Config, mpv: MPV):
        self._enabled = config.static_time > 0
        self._mpv = mpv
        if self._enabled:
            self._event: threading.Event = threading.Event()
            self._overlays: list[Overlay] = []
            logger.debug(f"Generating {self.NUM_OVERLAYS} random static overlays ({mpv.width}x{mpv.height})")
            for _ in range(self.NUM_OVERLAYS):
                array = numpy.random.randint(0, 0xFF + 1, mpv.shape, dtype=numpy.uint8)
                array[:, :, -1] = 0xFF
                overlay = mpv.create_overlay(STATIC_LAYER, array, add_pygame_surface=False)  # All the same layer num
                self._overlays.append(overlay)
            logger.debug(f"Done generating {self.NUM_OVERLAYS} random static overlays")

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
            self._mpv.clear_overlay(STATIC_LAYER)

    def start(self):
        if self._enabled:
            self._event.set()

    def stop(self):
        if self._enabled and self._event.is_set():  # Not threadsafe but only Player.player_thread is calling
            self._event.clear()


class Player:
    def __init__(self, config: Config, videos_db: VideosDB, mpv: MPV):
        self._mpv = mpv
        self._config = config
        self._videos_db = videos_db
        self.static = Static(config=config, mpv=mpv)
        self.static.start()
        self._generate_no_videos_overlay()

    def _generate_no_videos_overlay(self):
        self._no_videos_overlay: Overlay = self._mpv.create_overlay(NO_FILES_LAYER)
        text, rect = self._mpv.render_multiple_lines(
            (
                {"text": "No video files detected!", "size": 58},
                {"text": "Waiting. Please insert USB drive with videos.", "size": 36, "style": freetype.STYLE_OBLIQUE},
            ),
            bgcolor=BLACK,
            padding=10,
            padding_between=25,
        )
        self._no_videos_overlay.surf.fill(BLACK)
        rect.center = self._no_videos_overlay.rect.center
        self._no_videos_overlay.surf.blit(text, rect)
        self._no_videos_overlay_shown = False

    def _no_videos_text(self, show=True):
        if show and not self._no_videos_overlay_shown:
            self._no_videos_overlay.update()
            self._no_videos_overlay_shown = True
        elif not show and self._no_videos_overlay_shown:
            self._no_videos_overlay.clear()
            self._no_videos_overlay_shown = False

    def player_thread(self):
        clock = FPSClock()
        timeout = tick() + self._config.static_time
        video: None | Video = None
        state = PlayerState.STATIC
        play_state = PlayState.NOT_PLAYING

        position = duration = 0.0

        def play_next():
            nonlocal video, state, play_state, timeout, position, duration
            position = duration = 0.0
            video = self._videos_db.get_random_video()
            if video is None:
                self.static.stop()
                logger.trace("Warning: No videos found!")
                state = PlayerState.NEEDS_FILES
                play_state = PlayState.NOT_PLAYING
            else:
                self._no_videos_text(show=False)
                state = PlayerState.PLAYING
                play_state = PlayState.LOADING
                logger.info(f"Playing {video.path}")
                self._mpv._player.loadfile(str(video.path))
                timeout = tick() + 10  # 10 seconds to load

        i = 0
        while True:
            match state:
                case PlayerState.STATIC:
                    if tick() > timeout:
                        self.static.stop()
                        play_next()

                case PlayerState.NEEDS_FILES:
                    self._no_videos_text(show=True)
                    play_next()

                case PlayerState.PLAYING:
                    if play_state == PlayState.LOADING:
                        if not self._mpv.core_idle:
                            self.static.stop()
                            logger.debug("core-idle now false")
                            play_state = PlayState.PLAYING
                            self._mpv._player.seek(self._mpv._player.duration - 15.0)
                        elif tick() > timeout:
                            logger.info(f"Failed to start {video.path} in time. Marking as failed.")
                            # XXX TODO

                    else:
                        if self._mpv.core_idle:
                            position = duration = 0.0
                            self.static.start()
                            state = PlayerState.STATIC
                            play_state = PlayState.NOT_PLAYING
                            timeout = tick() + self._config.static_time
                        else:
                            position = self._mpv._player.time_pos
                            duration = self._mpv._player.duration

            logger.critical(
                f"core-idle={self._mpv.core_idle} path={video.path.stem if video else 'none'} {position=} {duration=}"
            )

            clock.tick(12)
            if (i := i + 1) > 12:
                pass  # Broadcast stats
                i = 0

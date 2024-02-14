import enum
import logging
import queue
import random
import threading
import time

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
    LOADING = "loading"
    NEEDS_FILES = "needs-files"
    PLAYING = "playing"
    PAUSED = "paused"


class BreakVideoPlayLoop(Exception):
    pass


class Static:
    NUM_OVERLAYS = 15
    NUM_NO_REPEATS = 7

    def __init__(self, config: Config, mpv: MPV):
        self.enabled = config.static_time > 0.0
        if self.enabled > 0:
            self._event: threading.Event = threading.Event()
            self._overlays: list[Overlay] = []
            self._mpv: MPV = mpv
            self._config: Config = config
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
        if self.enabled:
            self._event.set()

    def stop(self):
        if self.enabled:
            self._event.clear()

    def sleep(self, short: bool = False):
        if self.enabled:
            time.sleep(self._config.static_time / 5 if short else self._config.static_time)


class Player:
    def __init__(self, config: Config, videos_db: VideosDB, mpv: MPV, event_queue: queue.Queue):
        self._mpv: MPV = mpv
        self._config: Config = config
        self._videos_db: VideosDB = videos_db
        self._shared_data_lock: threading.Lock = threading.Lock()
        self._event_queue: queue.Queue = event_queue
        self.static: Static = Static(config=config, mpv=mpv)
        self.static.start()
        self._generate_no_videos_overlay()
        self._reset_state()
        self._num_state_keys = len(self.state)

        self.state: dict[str, Video | PlayerState | float]

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

    def _update_state(self, **kwargs):
        self.state = {**self.state, **kwargs}
        if len(self.state) != self._num_state_keys:
            raise Exception("State should only contain 4 keys! Something went wrong!")
        # logger.critical(f"{self.state = }")

    def _reset_state(self):
        self.state = {"duration": 0.0, "position": 0.0, "state": PlayerState.LOADING, "video": None}

    def _event_queue_iter(self):
        while True:
            yield self._event_queue.get()

    def player_thread(self):
        video: None | Video = None
        next_video: None | Video = None

        while True:
            self._reset_state()  # Reset state
            if self._config.static_time > 0:
                self.static.start()
                self.static.sleep(short=next_video is not None)

            video = self._videos_db.get_random_video() if next_video is None else next_video
            next_video = None

            if video is not None:
                logger.info(f"Playing {video.path}")
                self._mpv.play(video)

                try:
                    while True:
                        for event in self._event_queue_iter():
                            match event["event"]:
                                case "file-loaded":
                                    self._update_state(
                                        video=video, position=0.0, duration=0.0, state=PlayerState.PLAYING
                                    )
                                    self.static.stop()
                                case "position":
                                    self._update_state(position=event["value"])
                                case "duration":
                                    self._update_state(duration=event["value"])
                                case "paused":
                                    if event["value"] and self.state["state"] == PlayerState.PLAYING:
                                        self._update_state(state=PlayerState.PAUSED)
                                    elif not event["value"] and self.state["state"] == PlayerState.PAUSED:
                                        self._update_state(state=PlayerState.PLAYING)
                                case "end-file":
                                    logger.critical(f"end-file: {event}")
                                    raise BreakVideoPlayLoop
                                case "keypress":
                                    match event["action"]:
                                        case "enter":
                                            self._mpv.stop()
                                        case "up" | "down":
                                            add = 1 if event["action"] == "up" else -1
                                            next_video = self._videos_db.get_video_for_channel(video.channel + add)
                                            self._mpv.stop()
                                        case "right" | "left":
                                            multiplier = 1 if event["action"] == "right" else -1
                                            self._mpv.seek(multiplier * 30.0)
                                        case _:
                                            logger.critical(f"Uknown keypress: {event['action']}")

                                case _:
                                    logger.critical(f"Unknown event: {event}")
                except BreakVideoPlayLoop:
                    pass

            else:
                self._update_state(video=None, position=0.0, duration=0.0, state=PlayerState.NEEDS_FILES)
                self.static.stop()
                self._no_videos_overlay.update()
                self._videos_db.has_videos_event.wait()
                self._no_videos_overlay.clear()

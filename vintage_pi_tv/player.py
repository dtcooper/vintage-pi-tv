import enum
import logging
import queue
import random
import threading
import time
from time import monotonic as tick

import numpy
import numpy.typing
from pygame import freetype

from .config import Config
from .constants import BLACK, BLACK_SEETHRU, NO_FILES_LAYER, OSD_LAYER, STATIC_LAYER, TRANSPARENT, YELLOW
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
        self._mpv.clear_overlay(STATIC_LAYER)
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

                clock.tick(random.randint(18, 30))
            self._mpv.clear_overlay(STATIC_LAYER)

    def start(self):
        self._event.set()

    def stop(self):
        self._event.clear()


class OSD:
    def __init__(self, mpv: MPV, state_getter):
        self._state_getter = state_getter
        self._mpv: MPV = mpv
        self._show_until: float = -1.0
        self._show_volume_until: float = -1.0
        self._overlay = mpv.create_overlay(OSD_LAYER)

    def osd_thread(self):
        self._overlay.clear()
        clock = FPSClock()
        shown = True

        while True:
            # show = tick() <= self._show_until
            # show_volume = tick() <= self._show_volume_until
            state = self._state_getter()

            show = True
            show_volume = True
            if state["video"] and (show or show_volume):

                self._overlay.surf.fill(TRANSPARENT)
                surf, chan_rect = self._mpv.render_text(
                    str(state["video"].channel), 72, bgcolor=BLACK_SEETHRU, padding=10, style=freetype.STYLE_WIDE
                )
                chan_rect.topleft = self._mpv.scale_pixels(15, 15)
                self._overlay.surf.blit(surf, chan_rect)

                surf, name_rect = self._mpv.render_text(
                    state["video"].name,
                    32,
                    color=YELLOW,
                    bgcolor=BLACK_SEETHRU,
                    padding=8,
                    style=freetype.STYLE_OBLIQUE,
                )
                name_rect.topleft = chan_rect.bottomleft
                self._overlay.surf.blit(surf, name_rect)

                self._overlay.update()
                shown = True
            else:
                if shown:
                    self._overlay.clear()
                    shown = False
            clock.tick(18)


class Player:
    def __init__(self, config: Config, videos_db: VideosDB, mpv: MPV, event_queue: queue.Queue):
        self._mpv: MPV = mpv
        self._config: Config = config
        self._videos_db: VideosDB = videos_db
        self._shared_data_lock: threading.Lock = threading.Lock()
        self._event_queue: queue.Queue = event_queue
        self.state: dict[str, Video | PlayerState | float]
        self._reset_state()

        self.osd: OSD = OSD(mpv=mpv, state_getter=self._state_getter)
        self.static: Static = Static(config=config, mpv=mpv)
        self.static.start()
        self._generate_no_videos_overlay()

        self._num_state_keys = len(self.state)

    def _state_getter(self):
        return self.state

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
            if next_video is not None and self._config.static_time_between_channels > 0.0:
                self.static.start()
                time.sleep(self._config.static_time_between_channels)
            elif next_video is None and self._config.static_time > 0.0:
                self.static.start()
                time.sleep(self._config.static_time)

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

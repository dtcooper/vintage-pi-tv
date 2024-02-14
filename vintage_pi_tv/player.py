from contextlib import contextmanager
import enum
import logging
import queue
import random
import threading
from time import monotonic as tick

import numpy
import numpy.typing
import pygame

from .config import Config
from .constants import (
    BLACK,
    BLACK_SEETHRU,
    BLUE,
    NO_FILES_LAYER,
    OSD_LAYER,
    OSD_PROGRESS_BAR_LAYER,
    OSD_VOLUME_LAYER,
    STATIC_LAYER,
    TRANSPARENT,
    WHITE,
    YELLOW,
)
from .keyboard import Keyboard
from .mpv_wrapper import MPV, Overlay
from .utils import FPSClock, format_seconds, high_precision_sleep, is_docker
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
        import math  # XXX

        self._show_until: float = math.inf
        self._show_volume_until: float = math.inf
        self._show_progress_bar_until: float = math.inf
        self._osd_overlay = mpv.create_overlay(OSD_LAYER)
        self._progress_bar_overlay = mpv.create_overlay(OSD_PROGRESS_BAR_LAYER)
        self._volume_overlay = mpv.create_overlay(OSD_VOLUME_LAYER)
        self._last_osd_value = None
        self._last_progress_bar_value = None
        self._last_volume_value = None

    def _show_osd(self, state):
        channel, name = cache_try = (str(state["video"].channel + 1), state["video"].name)
        name = "asdjbasjkdbasdk" * 100
        if len(name) > 58:
            name = f"{name[:57]}\u2026"
        if cache_try != self._last_osd_value:
            self._osd_overlay.surf.fill(TRANSPARENT)
            surf, chan_rect = self._mpv.render_text(channel, 120, bgcolor=BLACK_SEETHRU, padding=10, style="bold")
            chan_rect.topleft = self._mpv.scale_pixels(15, 15)
            self._osd_overlay.surf.blit(surf, chan_rect)

            surf, name_rect = self._mpv.render_text(
                name,
                32,
                color=YELLOW,
                bgcolor=BLACK_SEETHRU,
                padding=8,
                style="italic",
            )
            name_rect.topleft = chan_rect.bottomleft
            self._osd_overlay.surf.blit(surf, name_rect)

            self._osd_overlay.update()
            self._last_osd_value = cache_try

    def _show_progress_bar(self, state):
        position, duration = cache_try = (round(state["position"] or 0), round(state["duration"] or 0))
        if cache_try != self._last_progress_bar_value:
            self._progress_bar_overlay.surf.fill(TRANSPARENT)
            surf, pos_rect = self._mpv.render_text(format_seconds(position), 25, padding=5, bgcolor=BLACK_SEETHRU)
            pos_rect.bottomleft = (self._mpv.scale_pixels(20), self._mpv.height - 1 - self._mpv.scale_pixels(20))
            self._progress_bar_overlay.surf.blit(surf, pos_rect)
            surf, dur_rect = self._mpv.render_text(format_seconds(duration), 25, padding=5, bgcolor=BLACK_SEETHRU)
            dur_rect.bottomright = (self._mpv.width - 1 - self._mpv.scale_pixels(20), pos_rect.bottom)
            self._progress_bar_overlay.surf.blit(surf, dur_rect)
            bar_rect = pygame.Rect(
                0,
                0,
                dur_rect.left - pos_rect.right - self._mpv.scale_pixels(20) - 1,
                dur_rect.height - self._mpv.scale_pixels(10),
            )
            bar_rect.centery = dur_rect.centery
            bar_rect.left = pos_rect.right + self._mpv.scale_pixels(10)
            pygame.draw.rect(self._progress_bar_overlay.surf, WHITE, bar_rect)
            if duration > 0.0:
                bar_rect.width = position / duration * bar_rect.width
                pygame.draw.rect(self._progress_bar_overlay.surf, BLUE, bar_rect)

            self._progress_bar_overlay.update()
            self._last_progress_bar_value = cache_try

    def _show_volume(self, state):
        pass

    def _clear_osd(self):
        self._last_osd_value = None
        self._osd_overlay.clear()

    def _clear_progress_bar(self):
        self._last_progress_bar_value = None
        self._progress_bar_overlay.clear()

    def _clear_volume(self):
        self._last_volume_value = None
        self._volume_overlay.clear()

    def osd_thread(self):
        self._clear_osd()
        self._clear_progress_bar()
        self._clear_volume()
        clock = FPSClock()

        while True:
            # show = tick() <= self._show_until
            # show_volume = tick() <= self._show_volume_until
            state = self._state_getter()

            now = tick()
            show_volume = self._show_until > now
            show_progress_bar = self._show_progress_bar_until > now
            show_osd = show_volume or show_progress_bar or self._show_until > now
            if state["video"] and show_osd:
                self._show_osd(state)
                if show_progress_bar:
                    self._show_progress_bar(state)
                else:
                    self._clear_progress_bar()

                if show_volume:
                    self._show_volume(state)
                else:
                    self._clear_volume()
            else:
                self._clear_osd()
                self._clear_progress_bar()
                self._clear_volume()
            clock.tick(24)


@contextmanager
def _block_keyboard(self: "Player"):
    if self._keyboard is not None:
        self._keyboard.blocked = True
        try:
            yield
        finally:
            self._keyboard.blocked = False
    elif self._config.keyboard["enabled"] and is_docker():
        self._mpv.docker_keyboard_blocked = True
        try:
            yield
        finally:
            self._mpv.docker_keyboard_blocked = False
    else:
        yield


class Player:
    def __init__(
        self,
        config: Config,
        videos_db: VideosDB,
        mpv: MPV,
        keyboard: None | Keyboard,
        event_queue: queue.Queue,
        state_updates_queue: queue.Queue,
    ):
        self._mpv: MPV = mpv
        self._config: Config = config
        self._videos_db: VideosDB = videos_db
        self._shared_data_lock: threading.Lock = threading.Lock()
        self._event_queue: queue.Queue = event_queue
        self._keyboard: None | Keyboard = keyboard
        self.state: dict[str, Video | PlayerState | float]
        self._state_updates_queue: queue.Queue = state_updates_queue
        self._reset_state()

        self.osd: OSD = OSD(mpv=mpv, state_getter=self._state_getter)
        self.static: Static = Static(config=config, mpv=mpv)
        self._generate_no_videos_overlay()

        self._num_state_keys = len(self.state)

    def _state_getter(self) -> dict:
        return self.state

    def _generate_no_videos_overlay(self):
        self._no_videos_overlay: Overlay = self._mpv.create_overlay(NO_FILES_LAYER)
        text, rect = self._mpv.render_multiple_lines(
            (
                {"text": "No video files detected!", "size": 58},
                {"text": "Waiting. Please insert USB drive with videos.", "size": 36, "style": "italic"},
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
        self._publish_state()

    def _reset_state(self):
        self.state = {"duration": 0.0, "position": 0.0, "state": PlayerState.LOADING, "video": None}
        self._publish_state()

    def _publish_state(self):
        state = self.state
        self._state_updates_queue.put({
            **state,
            "video": state["video"] and state["video"].serialize(),
        })

    def _event_queue_iter(self):
        while True:
            yield self._event_queue.get()

    def _handle_keypress(self, video: Video, event: dict) -> None | Video:
        next_video: None | Video = None
        logger.debug(f"Got key press event: {event}")
        match event["action"]:
            case "random":
                self._mpv.stop()
            case "pause":
                if self.state["state"] == PlayerState.PAUSED:
                    self._mpv.resume()
                elif self.state["state"] == PlayerState.PLAYING:
                    self._mpv.pause()
            case "up" | "down":
                add = 1 if event["action"] == "up" else -1
                next_video = self._videos_db.get_video_for_channel(video.channel + add)
                self._mpv.stop()
            case "right" | "left":
                multiplier = 1 if event["action"] == "right" else -1
                self._mpv.seek(multiplier * 30.0)
            case _:
                logger.critical(f"Uknown keypress: {event['action']}")
        return next_video

    def player_thread(self):
        video: None | Video = None
        next_video: None | Video = None

        # Unblock keyboard
        if self._keyboard is not None:
            self._keyboard.blocked = False
        elif self._config.keyboard["enabled"] and is_docker():
            self._mpv.docker_keyboard_blocked = False

        while True:
            self._reset_state()
            static_time = None

            if next_video is not None and self._config.static_time_between_channels > 0.0:
                static_time = self._config.static_time_between_channels
            elif next_video is None and self._config.static_time > 0.0:
                static_time = self._config.static_time
            if static_time is not None:
                with _block_keyboard(self):
                    self.static.start()
                    high_precision_sleep(static_time)

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
                                    if event["reason"] == "error":
                                        logger.warning(f"Error with video {video.path}. Disabling it.")
                                        self._videos_db.mark_bad_video(video)
                                    raise BreakVideoPlayLoop
                                case "keypress":
                                    next_video = self._handle_keypress(video, event)
                                case _:
                                    logger.critical(f"Unknown event: {event}")
                except BreakVideoPlayLoop:
                    pass

            else:
                self._update_state(video=None, position=0.0, duration=0.0, state=PlayerState.NEEDS_FILES)
                with _block_keyboard(self):
                    self.static.stop()
                    self._no_videos_overlay.update()
                    self._videos_db.has_videos_event.wait()
                    self._no_videos_overlay.clear()

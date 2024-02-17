from collections import defaultdict
from contextlib import contextmanager
import logging
from pathlib import Path
import queue
import random
import subprocess
import threading
import time

import numpy
import numpy.typing

from .config import Config
from .constants import BLACK, NO_FILES_LAYER, RED, STATIC_LAYER, PlayerState
from .keyboard import Keyboard
from .mpv_wrapper import MPV, Overlay
from .osd import OSD
from .utils import FPSClock, exit, is_docker
from .videos import Video, VideosDB


logger = logging.getLogger(__name__)


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
        websocket_updates_queue: queue.Queue,
    ):
        self._mpv: MPV = mpv
        self._config: Config = config
        self._videos_db: VideosDB = videos_db
        self._shared_data_lock: threading.Lock = threading.Lock()
        self._event_queue: queue.Queue = event_queue
        self._keyboard: None | Keyboard = keyboard
        self._current_rating: False | str = self._config.starting_rating
        self.state: dict[str, Video | PlayerState | float]
        self._websocket_updates_queue: queue.Queue = websocket_updates_queue
        if self._config.save_place_while_browsing:
            self._places: defaultdict[Path, float] = defaultdict(float)

        self._reset_state()
        self.osd: OSD = OSD(config=config, mpv=mpv, state_getter=self._state_getter)
        self.static: Static = Static(config=config, mpv=mpv)
        self._generate_no_videos_overlay()

        self._num_state_keys = len(self.state)
        self._websocket_updates_queue.put({"type": "current_rating", "data": self._current_rating})

    def _state_getter(self) -> dict:
        return self.state

    def _generate_no_videos_overlay(self):
        self._no_videos_overlay: Overlay = self._mpv.create_overlay(NO_FILES_LAYER)
        self._no_videos_overlay.surf.fill(BLACK)
        text, rect = self._mpv.render_multiple_lines_of_text(
            (
                {"text": "No video files detected!", "size": 58, "color": RED, "bgcolor": BLACK, "font": "bold"},
                {
                    "text": "You may need to insert a USB drive containing videos...",
                    "size": 28,
                    "bgcolor": BLACK,
                    "font": "bold-italic",
                },
            ),
            padding_between=20,
        )
        rect.center = self._no_videos_overlay.rect.center
        self._no_videos_overlay.surf.blit(text, rect)

    def _no_videos_text(self, show=True):
        if show and not self._no_videos_overlay.shown:
            self._no_videos_overlay.update()
        elif not show:
            self._no_videos_overlay.clear()

    def _update_state(self, **kwargs):
        self.state = {**self.state, **kwargs}
        if len(self.state) != self._num_state_keys:
            raise Exception("State should only contain 4 keys! Something went wrong!")
        self._publish_state()

    def _reset_state(self):
        state = {"duration": 0.0, "position": 0.0, "state": PlayerState.LOADING, "video": None}
        if self._config.show_fps:
            state.update({"fps_video": 0.0, "fps_actual": 0.0, "fps_dropped": 0})
        self.state = state
        self._publish_state()

    def _publish_state(self):
        state = self.state
        if (
            self._config.save_place_while_browsing
            and state["video"] is not None
            and state["state"] in (PlayerState.PLAYING, PlayerState.PAUSED)
        ):
            self._places[state["video"].path] = state["position"]
        self._websocket_updates_queue.put({
            "type": "state",
            "data": {
                **state,
                "video": state["video"] and state["video"].serialize(),
            },
        })

    def _event_queue_iter(self):
        while True:
            yield self._event_queue.get()

    def _clear_event_queue(self):
        try:
            while True:
                purged_event = self._event_queue.get_nowait()
                logger.trace(f"Purged event while clearing event queue: {purged_event}")
        except queue.Empty:
            pass

    def _handle_user_action(self, video: Video, event: dict) -> None | Video:
        next_video: None | Video = None
        logger.debug(f"Got key press event: {event}")
        match event["action"]:
            case "osd":
                _, muted = self._mpv.volume
                self.osd.show(progress_bar=True, volume=muted)
            case "random":
                self._update_state(video=None, state=PlayerState.LOADING)
                self._mpv.stop()
            case "pause":
                if self.state["state"] == PlayerState.PAUSED:
                    self._mpv.resume()
                elif self.state["state"] == PlayerState.PLAYING:
                    self._mpv.pause()
            case "up" | "down":
                self._update_state(video=None, state=PlayerState.LOADING)
                direction = 1 if event["action"] == "up" else -1
                next_video = self._videos_db.get_video_for_channel_change(
                    video=video, current_rating=self._current_rating, direction=direction
                )
                if next_video is None:
                    self.osd.notify(f"No channel found for rating {self._current_rating}!", color=RED)
                self._mpv.stop()
            case "right" | "left":
                multiplier = 1 if event["action"] == "right" else -1
                self._mpv.seek(multiplier * 15.0)
                self.osd.show(progress_bar=True)
            case "rewind":
                self._mpv.seek(0.0, absolute=True)
                self.osd.show(progress_bar=True)
            case "volume-up" | "volume-down":
                amount = 5 * (1 if event["action"] == "volume-up" else -1)
                self._mpv.change_volume(amount)
                self.osd.show(volume=True)
            case "mute":
                self._mpv.toggle_mute()
                self.osd.show(volume=True)
            case "ratings":
                if self._config.ratings:  # Ratings disabled
                    num = self._config.ratings_dict[self._current_rating]["num"]
                    num = (num - 1) % len(self._config.ratings)
                    rating_dict = self._config.ratings[num]
                    self.set_rating(rating_dict["rating"])
            case "power":
                if self._config.power_key_shutdown:
                    logger.warning("Attempting to power off machine")
                    try:
                        subprocess.check_call(("poweroff",))
                    except subprocess.CalledProcessError:
                        pass
                    exit(0, "Powered off machine")
                else:
                    exit(0, "Shut down by request")
            case _:
                logger.critical(f"Unknown keypress: {event['action']}")
        return next_video

    def set_rating(self, rating: str):
        if rating in self._config.ratings_dict:
            self._current_rating = rating
            rating_dict = self._config.ratings_dict[rating]
            color = rating_dict["color"]
            description = rating_dict["description"]
            logger.info(f"Current rating changed to {self._current_rating} ({description})")
            self.osd.notify(
                [
                    {
                        "text": f"Max rating: {rating}",
                        "size": 50,
                        "padding": (10, 10, 5, 10),
                        "color": color,
                        "font": "bold",
                    },
                    {
                        "text": rating_dict["description"],
                        "size": 32,
                        "padding": (5, 10, 10, 10),
                        "color": color,
                        "font": "italic",
                    },
                ],
                padding_between=0,
                align="right",
            )
            self._websocket_updates_queue.put({"type": "current_rating", "data": rating})
        else:
            logger.warning(f"Won't set rating to {rating}, since it doesn't exist!")

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

            self.static.start()  # May as well show a tiny bit of static during loading, even if it's disabled
            if next_video is not None and self._config.static_time_between_channels > 0.0:
                static_time = self._config.static_time_between_channels
            elif next_video is None and self._config.static_time > 0.0:
                static_time = self._config.static_time
            if static_time is not None:
                with _block_keyboard(self):
                    time.sleep(static_time)

            if next_video is None:
                video = self._videos_db.get_random_video(current_rating=self._current_rating)
                if video is None:
                    video = self._videos_db.get_random_video()  # Select from entire set
                    if video is not None:
                        self.osd.notify(f"No video found for rating {self._current_rating}!", color=RED)
            else:
                video = next_video
                next_video = None

            if video is not None:
                logger.info(f"Playing {video.path}")

                pre_seek = None
                if self._config.save_place_while_browsing:
                    pre_seek = self._places[video.path]
                self._mpv.play(video, pre_seek=pre_seek)

                try:
                    while True:
                        for event in self._event_queue_iter():
                            logger.trace(f"Got play event: {event}")
                            match event["event"]:
                                case "file-loaded":
                                    self._update_state(
                                        video=video, position=0.0, duration=0.0, state=PlayerState.PLAYING
                                    )
                                    self.static.stop()
                                    self.osd.show()
                                case "position" | "duration" | "fps-video" | "fps-actual" | "fps-dropped":
                                    self._update_state(**{event["event"].replace("-", "_"): event["value"]})
                                case "paused":
                                    if event["value"] and self.state["state"] == PlayerState.PLAYING:
                                        self._update_state(state=PlayerState.PAUSED)
                                    elif not event["value"] and self.state["state"] == PlayerState.PAUSED:
                                        self._update_state(state=PlayerState.PLAYING)
                                case "end-file":
                                    if (
                                        self.state["state"] == PlayerState.PLAYING
                                        and self._config.save_place_while_browsing
                                    ):
                                        self._places[video.path] = 0.0  # Reset place to zero
                                    if event["reason"] == "error":
                                        logger.warning(f"Error with video {video.path}. Disabling it.")
                                        self._videos_db.mark_bad_video(video)
                                    logger.info(f"Ending playback of {video.path}")
                                    raise BreakVideoPlayLoop
                                case "user-action":
                                    next_video = self._handle_user_action(video, event)
                                case "crash-player-thread":
                                    raise Exception("Crashed player thread on purpose.")
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

    def player_thread_cleanup(self):
        logger.info("Cleaning up player before restarting thread.")
        self._mpv.stop()
        time.sleep(0.5)
        self._clear_event_queue()

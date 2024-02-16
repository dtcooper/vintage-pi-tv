import logging
import queue
from typing import Literal

import mpv
import numpy
import numpy.typing
import pygame
import pygame.freetype

from .config import Config
from .constants import BLACK_SEETHRU, DATA_DIR, DOCKER_DEV_KEYBOARD_KEYS, TRANSPARENT, WHITE
from .utils import TRACE, exit, is_docker
from .videos import Video


logger = logging.getLogger(__name__)


MPV_LOG_LEVEL_MAPPING = {
    "fatal": logging.CRITICAL,
    "error": logging.ERROR,
    "warn": logging.WARNING,
    "info": logging.INFO,
    "status": logging.INFO,
    "v": logging.DEBUG,
    "debug": TRACE,
}

LOG_LEVEL_MPV_MAPPING = {
    "CRITICAL": "fatal",
    "ERROR": "error",
    "WARNING": "warn",
    "INFO": "status",
    "DEBUG": "v",
    "TRACE": "debug",
}


def mpv_log(level, prefix, text):
    logger.log(MPV_LOG_LEVEL_MAPPING.get(level, logging.INFO), f"[mpv/{prefix}] {text.rstrip()}")


class Overlay:
    def __init__(self, mpv: "MPV", num: int, array: None | numpy.typing.ArrayLike, add_pygame_surface: bool = True):
        # Instantiate via mpv.init_overlay()
        self._array: numpy.typing.ArrayLike = numpy.zeros(mpv.shape, dtype=numpy.uint8) if array is None else array
        self.surf: None | pygame.Surface = None
        self.rect: None | pygame.Rect = None
        if add_pygame_surface:
            self.surf = pygame.image.frombuffer(self._array, mpv.size, "BGRA")
            self.rect = self.surf.get_rect()
        self._mpv = mpv
        self._num = num
        self.shown = False

    def update(self):  # NOT THREADSAFE, should only be called from one thread because of self._show
        self._mpv._player.overlay_add(
            self._num,
            self._mpv._margin_left,
            self._mpv._margin_top,
            f"&{self._array.ctypes.data}",
            0,
            "bgra",
            self._mpv.width,
            self._mpv.height,
            self._mpv.width * 4,
        )
        self.shown = True

    def clear(self):
        if self.shown:
            self._mpv.clear_overlay(self._num)
            self.shown = False


class MPV:
    def __init__(self, config: Config, event_queue: queue.Queue):
        # Prep arguents for MPV
        kwargs = {k.replace("-", "_"): v for k, v in config.mpv_options.items() if not isinstance(v, bool) or v}
        if config.audio_visualization:
            kwargs.update({
                "scripts": str(DATA_DIR / "visualizer.lua"),
                "script_opts": "visualizer-name=avectorscope,visualizer-height=12",
            })
        if config.crt_filter:
            kwargs["glsl_shaders"] = str(DATA_DIR / "crt-filter.glsl")

        if config.aspect_mode == "zoom":
            logger.debug("Setting panscan to 1.0 for zoom")
            kwargs["panscan"] = "1.0"

        if config.keyboard["enabled"] and is_docker():
            kwargs["input_vo_keyboard"] = True

        logger.debug(f"Initializing MPV with arguments: {kwargs}")
        try:
            self._player: mpv.MPV = mpv.MPV(
                log_handler=mpv_log,
                loglevel=LOG_LEVEL_MPV_MAPPING[config.log_level],
                force_window="immediate",
                **kwargs,
            )
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
            exit(1, "mpv failed to initialize")

        self._event_queue: queue.Queue = event_queue

        @self._player.event_callback("file-loaded", "end-file")
        def _(event: mpv.MpvEvent):
            self._event_queue.put(event.as_dict(mpv.strict_decoder))

        @self._player.property_observer("time-pos")
        def _(_, value):
            self._event_queue.put({"event": "position", "value": value or 0.0})

        @self._player.property_observer("duration")
        def _(_, value):
            self._event_queue.put({"event": "duration", "value": value or 0.0})

        @self._player.property_observer("pause")
        def _(_, value):
            self._event_queue.put({"event": "paused", "value": value})

        if config.show_fps:

            @self._player.property_observer("estimated-vf-fps")
            def _(_, value):
                self._event_queue.put({"event": "fps-actual", "value": value or 0.0})

            @self._player.property_observer("container-fps")
            def _(_, value):
                self._event_queue.put({"event": "fps-video", "value": value or 0.0})

        if is_docker() and config.keyboard["enabled"]:
            self.docker_keyboard_blocked: bool = True  # Only modify in player thread
            for action, key in DOCKER_DEV_KEYBOARD_KEYS.items():
                self._enable_docker_key_binding(key, action)

        # Since we're primarily operating in fullscreen mode (except in development) window size should not be changed.
        # And if it does change, user is shit out of luck
        width: int = self._player.osd_width
        height: int = self._player.osd_height

        for margin, dimension in (("left", width), ("top", height), ("right", width), ("bottom", height)):
            if (pixels := config.overscan_margins[margin]) > 0:
                amount = pixels / dimension
                logger.debug(f"Set {margin} margin to {amount:0.5f} ({pixels}px)")
                setattr(self._player, f"video_margin_ratio_{margin}", amount)

        self._margin_left = config.overscan_margins["left"]
        self._margin_top = config.overscan_margins["top"]
        self.width: int = max(width - config.overscan_margins["left"] - config.overscan_margins["right"], 1)
        self.height: int = max(height - config.overscan_margins["top"] - config.overscan_margins["bottom"], 1)
        if config.aspect_mode == "stretch":
            aspect = self.width / self.height
            logger.debug(f"Set aspect ratio to {aspect} for stretch")
            self._player.video_aspect_override = str(aspect)

        logger.info(f"MPV initialized (screen: {width}x{height}, with margins: {self.width}x{self.height})")

        self.size: tuple[int, int] = (self.width, self.height)
        self.shape: tuple[int, int, int] = (self.width, self.height, 4)
        self._font_scale: float = min(self.width * 9 / 16, self.height) / 720
        self._pixel_scale: float = min(self.width * 9 / 16, self.height) / 360

        pygame.freetype.init()
        self._fonts: dict[pygame.freetype.Font] = {
            name: pygame.freetype.Font(DATA_DIR / "fonts" / f"space-mono-{name}.ttf")
            for name in ("regular", "italic", "bold", "bold-italic")
        }

        self._done_overlay = self.create_overlay(63)
        self._done_overlay.surf.fill("black")
        text, rect = self.render_text("Vintage Pi TV Loading...", 64, bgcolor=TRANSPARENT, font="bold-italic")
        rect.center = self._done_overlay.surf.get_rect().center
        self._done_overlay.surf.blit(text, rect)
        self._done_overlay.update()
        self._volume_cache: bool = 100
        self._mute_cache: bool = False

        if config.start_muted:
            self.toggle_mute()

    def scale_pixels(self, *n: list[int | float]):
        if len(n) == 1:
            return n[0] * self._pixel_scale
        else:
            return [i * self._pixel_scale for i in n]

    def _resolve_padding(
        self, padding: int | tuple[int, int] | tuple[int, int, int, int]
    ) -> None | tuple[int, int, int, int]:
        # Padding like CSS : int, [y, x], [top, right, bottom, left]
        if isinstance(padding, int):
            padding = (padding, padding, padding, padding)
        elif len(padding) == 2:
            padding = (padding[0], padding[1], padding[0], padding[1])

        if all(p == 0 for p in padding):
            return (0, 0, 0, 0)

        return self.scale_pixels(*padding)

    def render_text(
        self,
        text: str,
        size: int,
        color=WHITE,
        bgcolor=BLACK_SEETHRU,
        font: Literal["regular", "bold", "italic", "bold-italic"] = "regular",
        padding: int | tuple[int, int] | tuple[int, int, int, int] = 0,
    ) -> tuple[pygame.Surface, pygame.Rect]:
        top, right, bottom, left = self._resolve_padding(padding)
        has_padding = any(p != 0 for p in (top, left, bottom, left))
        surf, rect = self._fonts[font].render(
            text, fgcolor=color, bgcolor=TRANSPARENT if has_padding else bgcolor, size=size * self._font_scale
        )
        if not has_padding:
            return surf, rect

        new_surf = pygame.Surface((rect.width + left + right, rect.height + top + bottom), pygame.SRCALPHA)
        new_surf.fill(bgcolor)
        new_surf.blit(surf, (left, top))
        return new_surf, new_surf.get_rect()

    def render_multiple_lines_of_text(
        self,
        kwargs_to_render,
        align: Literal["left", "center", "right"] = "center",
        bgcolor=TRANSPARENT,
        padding: int | tuple[int, int] | tuple[int, int, int, int] = 0,
        padding_between: int = 0,
    ):
        texts = [self.render_text(**kwargs) for kwargs in kwargs_to_render]
        width = max(text[1].width for text in texts)
        height = sum(text[1].height for text in texts)
        top, right, bottom, left = self._resolve_padding(padding)

        padding_between = self.scale_pixels(padding_between)
        surf = pygame.Surface(
            (width + left + right, height + top + bottom + padding_between * (len(texts) - 1)), pygame.SRCALPHA
        )
        surf.fill(bgcolor)
        rect = surf.get_rect()
        y = top

        for text_surf, text_rect in texts:
            if align == "left":
                text_rect.left = left
            elif align == "center":
                text_rect.centerx = rect.centerx
            else:
                text_rect.right = rect.right - right
            text_rect.y = y
            surf.blit(text_surf, text_rect)
            y += text_rect.height + padding_between

        return surf, rect

    def create_overlay(
        self, num: int, array: None | numpy.typing.ArrayLike = None, add_pygame_surface: bool = True
    ) -> Overlay:
        return Overlay(self, num, array, add_pygame_surface)

    def clear_overlay(self, num: int):
        return self._player.overlay_remove(num)

    def done_loading(self):
        self._done_overlay.clear()
        del self._done_overlay

    def play(self, video: Video, pre_seek: None | float):
        if pre_seek is not None and pre_seek > 0.0:
            self._player.loadfile(str(video.path), start=pre_seek)
        else:
            self._player.loadfile(str(video.path))
        self.resume()

    def stop(self):
        self._player.stop()

    def pause(self):
        self._player.pause = True

    def resume(self):
        self._player.pause = False

    def seek(self, amount: float, absolute: bool = False):
        self._player.seek(amount, reference="absolute" if absolute else "relative")

    def change_volume(self, amount: int):
        self.set_volume(self._volume_cache + amount)

    def set_volume(self, value: int):
        if self._mute_cache:
            self.toggle_mute()
        volume = max(0, min(100, value))
        self._volume_cache = self._player.volume = volume

    def toggle_mute(self):
        new_value = not self._mute_cache
        self._player.mute = new_value
        self._mute_cache = new_value

    @property
    def volume(self) -> tuple[float, bool]:
        # TODO cache this, don't poll player
        return (self._volume_cache, self._mute_cache)

    if is_docker():

        def _enable_docker_key_binding(self, key, action):
            logger.debug(f"Enabling Mpv key {key} in Docker mode")

            @self._player.on_key_press(key)
            def _():
                if self.docker_keyboard_blocked:
                    logger.warning(f"Blocked keypress {key} by player request in Docker mode")
                else:
                    self._event_queue.put({"event": "user-action", "action": action})

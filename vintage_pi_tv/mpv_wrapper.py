import logging
from pathlib import Path
import sys
from typing import Literal

import mpv
import numpy
import pygame
import pygame.freetype

from .config import Config
from .constants import TRANSPARENT, WHITE
from .utils import TRACE


logger = logging.getLogger(__name__)


mpv_log_level_mapping = {
    "fatal": logging.CRITICAL,
    "error": logging.ERROR,
    "warn": logging.WARNING,
    "info": logging.INFO,
    "status": logging.INFO,
    "v": logging.DEBUG,
    "debug": TRACE,
}

log_level_mpv_mapping = {
    "CRITICAL": "fatal",
    "ERROR": "error",
    "WARNING": "warn",
    "INFO": "status",
    "DEBUG": "v",
    "TRACE": "debug",
}


def mpv_log(level, prefix, text):
    logger.log(mpv_log_level_mapping.get(level, logging.INFO), f"[mpv/{prefix}] {text.rstrip()}")


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

    def update(self):
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

    def clear(self):
        self._mpv._player.overlay_remove(self._num)


class MPV:
    def __init__(self, config: Config):
        # Prep arguents for MPV
        kwargs = {k.replace("-", "_"): v for k, v in config.mpv_options.items() if not isinstance(v, bool) or v}
        if config.enable_audio_visualization:
            kwargs.update({
                "scripts": str(Path(__file__).parent / "visualizer.lua"),
                "script_opts": "visualizer-name=avectorscope,visualizer-height=12",
            })

        if config.aspect_mode == "zoom":
            logger.debug("Setting panscan to 1.0 for zoom")
            kwargs["panscan"] = "1.0"

        logger.debug(f"Initializing MPV with arguments: {kwargs}")
        try:
            self._player: mpv.MPV = mpv.MPV(
                log_handler=mpv_log,
                loglevel=log_level_mpv_mapping[config.log_level],
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
            sys.exit(1)

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
        self.pixel_scale: float = min(self.width * 9 / 16, self.height) / 360

        pygame.freetype.init()
        self._font: pygame.freetype.Font = pygame.freetype.Font(Path(__file__).parent / "undefined-medium.ttf")

        self._done_overlay = self.create_overlay(63)
        self._done_overlay.surf.fill("black")
        text, rect = self.render_text("Loading...", 100)
        rect.center = self._done_overlay.surf.get_rect().center
        self._done_overlay.surf.blit(text, rect)
        self._done_overlay.update()

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

        return tuple(map(lambda p: p * self.pixel_scale, padding))

    def render_text(
        self,
        text: str,
        size: int,
        color=WHITE,
        bgcolor=TRANSPARENT,
        style=pygame.freetype.STYLE_DEFAULT,
        padding: int | tuple[int, int] | tuple[int, int, int, int] = 0,
    ) -> tuple[pygame.Surface, pygame.Rect]:
        surf, rect = self._font.render(text, fgcolor=color, bgcolor=bgcolor, size=size * self._font_scale, style=style)
        top, right, bottom, left = self._resolve_padding(padding)
        print(f"{text}: {top=}, {right=}, {bottom=}, {left=}")
        if all(p == 0 for p in (top, left, bottom, left)):
            return surf, rect

        new_surf = pygame.Surface((rect.width + left + right, rect.height + top + bottom), pygame.SRCALPHA)
        new_surf.fill(bgcolor)
        new_surf.blit(surf, (top, left))
        return new_surf, new_surf.get_rect()

    def render_multiple_lines(
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
        print(f"MULTIPLE: {top=}, {right=}, {bottom=}, {left=}")

        padding_between = padding_between * self.pixel_scale
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

    def done_loading(self):
        self._done_overlay.clear()
        self._done_overlay = None

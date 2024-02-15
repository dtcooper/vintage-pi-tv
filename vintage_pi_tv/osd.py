from functools import wraps
from time import monotonic as tick

import pygame

from .config import Config
from .constants import (
    BLACK_SEETHRU,
    BLUE,
    OSD_LAYER,
    OSD_PROGRESS_BAR_LAYER,
    OSD_VOLUME_LAYER,
    RED,
    TRANSPARENT,
    WHITE,
    YELLOW,
)
from .mpv_wrapper import MPV, Overlay
from .utils import FPSClock, format_seconds
from .videos import Video


def cached_show_method(method):
    cache_value = None

    @wraps(method)
    def wrapped(self, *args, **kwargs):
        nonlocal cache_value
        cache_value = method(self, *args, cache_value=cache_value, **kwargs)

    return wrapped


class OSD:
    def __init__(self, config: Config, mpv: MPV, state_getter):
        self._state_getter = state_getter
        self._config: Config = config
        self._mpv: MPV = mpv
        self._show_until: float = -1.0
        self._show_volume_until: float = -1.0
        self._show_progress_bar_until: float = -0.1
        self._osd: Overlay = mpv.create_overlay(OSD_LAYER)
        self._progress_bar: Overlay = mpv.create_overlay(OSD_PROGRESS_BAR_LAYER)
        self._volume: Overlay = mpv.create_overlay(OSD_VOLUME_LAYER)

    @cached_show_method
    def _show_osd(self, state, cache_value):
        video: Video = state["video"]
        if self._config.show_fps:
            channel, name, rating, fps = cache_try = (
                video.display_channel,
                video.name,
                video.rating,
                f"{state['fps_actual']:.2f}/{state['fps_video']:.2f}",
            )
        else:
            channel, name, rating = cache_try = (video.display_channel, video.name, video.rating)

        if len(name) > 58:
            name = f"{name[:57]}\u2026"
        if not self._osd.shown or cache_try != cache_value:
            self._osd.surf.fill(TRANSPARENT)
            text = [
                {"text": channel, "size": 120, "bgcolor": BLACK_SEETHRU, "padding": 10, "style": "bold"},
                {"text": name, "size": 32, "color": YELLOW, "bgcolor": BLACK_SEETHRU, "padding": 8, "style": "italic"},
            ]
            if self._config.show_fps:
                text.append({"text": f"{fps} fps", "size": 24, "bgcolor": BLACK_SEETHRU, "padding": (5, 8)})

            surf, rect = self._mpv.render_multiple_lines_of_text(text, align="left")
            rect.topleft = self._mpv.scale_pixels(15, 15)
            self._osd.surf.blit(surf, rect)

            if rating:
                color = video.rating_dict["color"]
                surf, rect = self._mpv.render_text(rating, 80, color=color, bgcolor=BLACK_SEETHRU, padding=9)
                rect.topright = (self._mpv.width - self._mpv.scale_pixels(15) - 1, self._mpv.scale_pixels(15))
                self._osd.surf.blit(surf, rect)

            self._osd.update()
        return cache_try

    @cached_show_method
    def _show_progress_bar(self, state, cache_value):
        position, duration = cache_try = (round(state["position"] or 0), round(state["duration"] or 0))
        if not self._progress_bar.shown or cache_try != cache_value:
            self._progress_bar.surf.fill(TRANSPARENT)
            surf, pos_rect = self._mpv.render_text(format_seconds(position), 25, padding=5, bgcolor=BLACK_SEETHRU)
            pos_rect.bottomleft = (self._mpv.scale_pixels(20), self._mpv.height - 1 - self._mpv.scale_pixels(20))
            self._progress_bar.surf.blit(surf, pos_rect)
            surf, dur_rect = self._mpv.render_text(format_seconds(duration), 25, padding=5, bgcolor=BLACK_SEETHRU)
            dur_rect.bottomright = (self._mpv.width - 1 - self._mpv.scale_pixels(20), pos_rect.bottom)
            self._progress_bar.surf.blit(surf, dur_rect)
            bar_rect = pygame.Rect(
                0,
                0,
                dur_rect.left - pos_rect.right - self._mpv.scale_pixels(20) - 1,
                dur_rect.height - self._mpv.scale_pixels(5),
            )
            bar_rect.centery = dur_rect.centery
            bar_rect.left = pos_rect.right + self._mpv.scale_pixels(10)
            pygame.draw.rect(self._progress_bar.surf, WHITE, bar_rect)
            if duration > 0.0:
                bar_rect.width = position / duration * bar_rect.width
                pygame.draw.rect(self._progress_bar.surf, BLUE, bar_rect)

            self._progress_bar.update()
        return cache_try

    @cached_show_method
    def _show_volume(self, cache_value):
        volume, mute = self._mpv.volume
        if mute:
            volume_str = cache_try = "mute"
            color = RED
        else:
            volume = round(volume)
            volume_str = cache_try = f"{volume: 3d}%"
            color = WHITE if volume > 0 else RED

        if not self._volume.shown or cache_try != cache_value:
            self._volume.surf.fill(TRANSPARENT)
            surf, vol_rect = self._mpv.render_text(
                f"Vol: {volume_str}", 44, padding=9, color=color, bgcolor=BLACK_SEETHRU
            )
            vol_rect.top = self._mpv.scale_pixels(15)
            vol_rect.centerx = (self._mpv.width - 1) // 2
            self._volume.surf.blit(surf, vol_rect)

            self._volume.update()
        return cache_try

    def show(self, duration=5.0, progress_bar=False, volume=False):
        until = tick() + duration
        self._show_until = until
        self._show_progress_bar_until = until if progress_bar else -0.1
        self._show_volume_until = until if volume else -1.0

    def osd_thread(self):
        self._osd.clear()
        self._progress_bar.clear()
        self._volume.clear()
        clock = FPSClock()

        while True:
            # show = tick() <= self._show_until
            # show_volume = tick() <= self._show_volume_until
            state = self._state_getter()

            now = tick()
            _, mute = self._mpv.volume
            show_volume = self._show_volume_until > now
            show_progress_bar = self._show_progress_bar_until > now
            show_osd = self._config.channel_osd_always_on or show_volume or show_progress_bar or self._show_until > now
            if state["video"] and show_osd:
                self._show_osd(state)
                if show_progress_bar:
                    self._show_progress_bar(state)
                else:
                    self._progress_bar.clear()

                if show_volume:
                    self._show_volume()
                else:
                    self._volume.clear()
            else:
                self._osd.clear()
                self._progress_bar.clear()
                self._volume.clear()
            clock.tick(24)

from functools import wraps
from time import monotonic as tick

import pygame

from .config import Config
from .constants import (
    BLUE,
    GREEN,
    OSD_LAYER,
    OSD_NOTIFY_LAYER,
    OSD_PROGRESS_BAR_LAYER,
    OSD_VOLUME_LAYER,
    RED,
    TRANSPARENT,
    WHITE,
    YELLOW,
    PlayerState,
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
        self._show_progress_bar_until: float = -1.0
        self._show_notify_until: float = -1.0
        if not self._config.disable_osd:
            self._osd: Overlay = mpv.create_overlay(OSD_LAYER)
        self._progress_bar: Overlay = mpv.create_overlay(OSD_PROGRESS_BAR_LAYER)
        self._volume: Overlay = mpv.create_overlay(OSD_VOLUME_LAYER)
        self._notify: Overlay = mpv.create_overlay(OSD_NOTIFY_LAYER)

    @cached_show_method
    def _show_osd(self, state, cache_value):
        video: Video = state["video"]
        if self._config.show_fps:
            channel, name, rating, fps = cache_try = (
                video.display_channel,
                video.name,
                video.rating,
                f"{state['fps_actual']:.2f}/{state['fps_video']:.2f}fps [{state['fps_dropped']} dropped]",
            )
        else:
            channel, name, rating = cache_try = (video.display_channel, video.name, video.rating)

        if len(name) > 58:
            name = f"{name[:57]}\u2026"
        if not self._osd.shown or cache_try != cache_value:
            self._osd.surf.fill(TRANSPARENT)
            text = [
                {"text": str(channel), "size": 120, "padding": (10, 10, 6, 10), "font": "bold"},
                {"text": name, "size": 32, "color": YELLOW, "padding": 8, "font": "italic"},
            ]
            if self._config.show_fps:
                text.append({"text": fps, "size": 22, "padding": (5, 7, 7, 7)})

            surf, rect = self._mpv.render_multiple_lines_of_text(text, align="left")
            rect.topleft = self._mpv.scale_pixels(15, 15)
            self._osd.surf.blit(surf, rect)

            if rating:
                color = video.rating_dict["color"]
                surf, rect = self._mpv.render_text(rating, 80, color=color, padding=15)
                pygame.draw.rect(surf, color, rect, width=round(self._mpv.scale_pixels(4.5)))
                rect.topright = (self._osd.rect.right - self._mpv.scale_pixels(15), self._mpv.scale_pixels(15))
                self._osd.surf.blit(surf, rect)

            self._osd.update()
        return cache_try

    @cached_show_method
    def _show_progress_bar(self, state, cache_value):
        is_paused = state["state"] == PlayerState.PAUSED
        show_paused = is_paused and (tick() % 2.2) < 1.6
        position, duration, _, _ = cache_try = (
            round(state["position"] or 0),
            round(state["duration"] or 0),
            is_paused,
            show_paused,
        )
        if not self._progress_bar.shown or cache_try != cache_value:
            color = RED if is_paused else WHITE
            self._progress_bar.surf.fill(TRANSPARENT)
            surf, pos_rect = self._mpv.render_text(format_seconds(position), 25, padding=5)
            pos_rect.bottomleft = (
                self._mpv.scale_pixels(20),
                self._progress_bar.rect.bottom - self._mpv.scale_pixels(20),
            )
            self._progress_bar.surf.blit(surf, pos_rect)
            surf, dur_rect = self._mpv.render_text(format_seconds(duration), 25, padding=5)
            dur_rect.bottomright = (self._progress_bar.rect.right - self._mpv.scale_pixels(20), pos_rect.bottom)
            self._progress_bar.surf.blit(surf, dur_rect)
            bar_rect = pygame.Rect(
                0,
                0,
                dur_rect.left - pos_rect.right - self._mpv.scale_pixels(20) - 1,
                dur_rect.height - self._mpv.scale_pixels(5),
            )
            bar_rect.centery = dur_rect.centery
            bar_rect.left = pos_rect.right + self._mpv.scale_pixels(10)
            pygame.draw.rect(self._progress_bar.surf, color, bar_rect)
            if duration > 0.0:
                bar_rect.width = position / duration * bar_rect.width
                pygame.draw.rect(self._progress_bar.surf, BLUE, bar_rect)
            if show_paused:
                surf, paused_rect = self._mpv.render_text("PAUSED!", 40, padding=8, color=color, font="bold-italic")
                paused_rect.centerx = self._progress_bar.rect.centerx
                paused_rect.bottom = bar_rect.top - self._mpv.scale_pixels(5)
                self._progress_bar.surf.blit(surf, paused_rect)

            self._progress_bar.update()
        return cache_try

    @cached_show_method
    def _show_volume(self, cache_value):
        volume, mute = self._mpv.volume
        if mute:
            volume_str = cache_try = "muted"
            color = RED
        else:
            volume = round(volume)
            volume_str = cache_try = f"{volume}%"
            if volume >= 100:
                color = GREEN
            elif 100 > volume > 0:
                color = WHITE
            else:
                color = RED

        if not self._volume.shown or cache_try != cache_value:
            self._volume.surf.fill(TRANSPARENT)
            surf, vol_rect = self._mpv.render_text(f"Vol: {volume_str}", 44, padding=9, color=color)
            vol_rect.top = self._mpv.scale_pixels(15)
            vol_rect.centerx = self._volume.rect.centerx
            self._volume.surf.blit(surf, vol_rect)

            self._volume.update()
        return cache_try

    def show(self, duration=5.0, progress_bar=False, volume=False):
        until = tick() + duration
        self._show_until = until
        if progress_bar:
            self._show_progress_bar_until = until
        if volume:
            self._show_volume_until = until

    def notify(self, text: str | list, duration: float = 10.0, **kwargs):
        self._show_notify_until = tick() + duration
        self._notify.surf.fill(TRANSPARENT)
        kwargs = {"padding": 10, **kwargs}  # Sane defaults
        if isinstance(text, str):
            kwargs = {"size": 50, **kwargs}
            text, surf = self._mpv.render_text(text, kwargs.pop("size", 50), **kwargs)
        else:
            kwargs = {"padding_between": 5, **kwargs}
            text, surf = self._mpv.render_multiple_lines_of_text(text, **kwargs)

        surf.center = self._notify.rect.center
        self._notify.surf.blit(text, surf)
        self._notify.update()

    def osd_thread(self):
        if not self._config.disable_osd:
            self._osd.clear()
        self._progress_bar.clear()
        self._volume.clear()
        clock = FPSClock()

        while True:
            state = self._state_getter()

            now = tick()
            is_paused = state["state"] == PlayerState.PAUSED
            show_volume = self._show_volume_until >= now
            show_progress_bar = is_paused or self._show_progress_bar_until >= now
            show_osd = self._config.channel_osd_always_on or show_volume or show_progress_bar or self._show_until >= now

            if now > self._show_notify_until:
                self._notify.clear()

            if state["video"] and show_osd:
                if not self._config.disable_osd:
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
                if not self._config.disable_osd:
                    self._osd.clear()
                self._progress_bar.clear()
                self._volume.clear()

            clock.tick(24)

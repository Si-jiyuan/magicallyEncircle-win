"""Replay a gesture using the same stroke pipeline as live drawing."""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, QTimer

from .model.gestures import Strokes
from .platform_support.overlay import OverlayWindow


class PatternPlayer(QObject):
    BASE_POINTS_PER_SECOND = 55.0

    def __init__(self) -> None:
        super().__init__()
        self._overlay: OverlayWindow | None = None
        self._strokes: Strokes = []
        self._stroke_index = 0
        self._point_index = 0
        self._accumulated = 0.0
        self._last_tick = 0.0
        self._points_per_second = self.BASE_POINTS_PER_SECOND
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    @property
    def is_playing(self) -> bool:
        return self._timer.isActive()

    def play(self, overlay: OverlayWindow, strokes: Strokes, speed: float) -> None:
        self.cancel()
        valid = [stroke for stroke in strokes if len(stroke) >= 2]
        if not valid:
            return
        self._overlay = overlay
        self._strokes = valid
        self._stroke_index = 0
        self._point_index = 0
        self._accumulated = 0.0
        self._last_tick = time.perf_counter()
        self._points_per_second = self.BASE_POINTS_PER_SECOND * max(0.05, speed)
        overlay.pins_strokes = True
        self._timer.start()

    def cancel(self) -> None:
        self._timer.stop()
        if self._overlay is not None:
            try:
                self._overlay.pins_strokes = False
                self._overlay.release_pinned_strokes(time.perf_counter())
            except RuntimeError:
                pass
        self._overlay = None
        self._strokes = []

    def _tick(self) -> None:
        overlay = self._overlay
        if overlay is None:
            self.cancel()
            return
        try:
            self._tick_overlay(overlay)
        except RuntimeError:
            self.cancel()

    def _tick_overlay(self, overlay: OverlayWindow) -> None:
        now = time.perf_counter()
        dt = now - self._last_tick
        self._last_tick = now
        self._accumulated += self._points_per_second * dt
        count = int(self._accumulated)
        if count <= 0:
            return
        self._accumulated -= count
        for _ in range(count):
            if not self._advance(overlay, now):
                self.cancel()
                return

    def _advance(self, overlay: OverlayWindow, now: float) -> bool:
        if self._stroke_index >= len(self._strokes):
            return False
        stroke = self._strokes[self._stroke_index]
        if self._point_index == 0:
            overlay.begin_stroke(stroke[0], now)
            self._point_index = 1
            return True
        if self._point_index < len(stroke):
            overlay.extend_stroke(stroke[self._point_index], now)
            self._point_index += 1
            if self._point_index >= len(stroke):
                overlay.finish_stroke(now)
                self._stroke_index += 1
                self._point_index = 0
            return True
        self._stroke_index += 1
        self._point_index = 0
        return self._stroke_index < len(self._strokes)

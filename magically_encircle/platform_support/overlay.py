"""Transparent, click-through overlay windows (one per monitor)."""

from __future__ import annotations

import logging
import math
import random
import time
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from ..constants import (
    FADE_DURATION,
    FRAME_INTERVAL,
    GUIDE_GROW_DURATION,
    GUIDE_INSET,
)
from ..model.gestures import Point
from . import win32

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class StyleColors:
    core: tuple[int, int, int]
    glow: tuple[int, int, int]
    particles: tuple[tuple[int, int, int], ...]


STYLES: dict[str, StyleColors] = {
    "whiteOrange": StyleColors(
        (255, 250, 235), (255, 140, 31), ((255, 255, 255), (255, 194, 77), (255, 128, 26))
    ),
    "whiteBlue": StyleColors(
        (255, 250, 235), (51, 153, 255), ((255, 255, 255), (140, 204, 255), (51, 153, 255))
    ),
    "whiteGreen": StyleColors(
        (255, 250, 235), (64, 230, 115), ((255, 255, 255), (153, 255, 179), (64, 230, 115))
    ),
    "whitePurple": StyleColors(
        (255, 250, 235), (158, 97, 255), ((255, 255, 255), (204, 166, 255), (158, 97, 255))
    ),
    "whitePink": StyleColors(
        (255, 250, 235), (255, 107, 184), ((255, 255, 255), (255, 179, 217), (255, 107, 184))
    ),
}

STYLE_TITLES: dict[str, str] = {
    "whiteOrange": "白橙发光 · 星尘粒子",
    "whiteBlue": "白蓝发光 · 星尘粒子",
    "whiteGreen": "白绿发光 · 星尘粒子",
    "whitePurple": "白紫发光 · 星尘粒子",
    "whitePink": "白粉发光 · 星尘粒子",
    "random": "随机风格（每笔随机）",
}


def resolve_style(name: str) -> str:
    if name == "random":
        return random.choice(list(STYLES))
    return name if name in STYLES else "whiteOrange"


def qcolor(rgb: tuple[int, int, int], alpha: float = 1.0) -> QColor:
    return QColor(rgb[0], rgb[1], rgb[2], max(0, min(255, int(alpha * 255))))


@dataclass
class MonitorInfo:
    device: str
    physical: tuple[int, int, int, int]  # left, top, right, bottom
    logical: QRectF
    screen: object  # QScreen
    dpr: float


@dataclass
class _Particle:
    position: QPointF
    vx: float
    vy: float
    born: float
    life: float
    size: float
    color: tuple[int, int, int]


@dataclass
class _Stroke:
    points: list[QPointF]
    start_time: float
    end_time: float | None
    style: str


class OverlayWindow(QWidget):
    def __init__(self, monitor: MonitorInfo) -> None:
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
            | Qt.WindowTransparentForInput,
        )
        self.monitor = monitor
        self._strokes: list[_Stroke] = []
        self._particles: list[_Particle] = []
        self._current: _Stroke | None = None
        self._style = "whiteOrange"
        self._timer = QTimer(self)
        self._timer.setInterval(max(1, int(FRAME_INTERVAL * 1000)))
        self._timer.timeout.connect(self._tick)
        self.pins_strokes = False
        self._guide_active = False
        self._guide_progress = 0.0
        self._guide_alpha = 0.0

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setGeometry(monitor.logical.toRect())
        self.show()
        self._apply_native_styles()

    # ------------------------------------------------------------------
    def _apply_native_styles(self) -> None:
        try:
            hwnd = int(self.winId())
            win32.set_overlay_native_styles(hwnd)
        except Exception:
            log.debug("Could not set overlay native styles", exc_info=True)

    def ensure_visible(self) -> None:
        """Re-assert topmost/click-through state, e.g. before drawing starts."""
        try:
            hwnd = int(self.winId())
            win32.set_overlay_native_styles(hwnd)
            self.raise_()
        except Exception:
            pass

    def set_style(self, style: str) -> None:
        self._style = style

    # ------------------------------------------------------------------
    def begin_stroke(self, point: Point, now: float) -> None:
        style = resolve_style(self._style)
        stroke = _Stroke([QPointF(point[0], point[1])], now, None, style)
        self._strokes.append(stroke)
        self._current = stroke
        self._spawn_particles(QPointF(point[0], point[1]), now, style)
        self._start_timer()
        self.update()

    def extend_stroke(self, point: Point, now: float) -> None:
        stroke = self._current
        if stroke is None:
            return
        qpoint = QPointF(point[0], point[1])
        if stroke.points:
            last = stroke.points[-1]
            if math.hypot(qpoint.x() - last.x(), qpoint.y() - last.y()) < 0.5:
                return
        stroke.points.append(qpoint)
        self._spawn_particles(qpoint, now, stroke.style)
        self.update()

    def finish_stroke(self, now: float) -> None:
        stroke = self._current
        if stroke is None:
            return
        if not self.pins_strokes:
            stroke.end_time = now
        self._current = None

    def release_pinned_strokes(self, now: float) -> None:
        for stroke in self._strokes:
            if stroke.end_time is None:
                stroke.end_time = now
        self._start_timer()

    def show_guide_lines(self) -> None:
        self._guide_active = True
        self._start_timer()
        self.update()

    def hide_guide_lines(self) -> None:
        self._guide_active = False
        self._start_timer()
        self.update()

    def clear(self) -> None:
        self._strokes.clear()
        self._particles.clear()
        self._current = None
        self._guide_active = False
        self._guide_alpha = 0.0
        self._guide_progress = 0.0
        self.update()

    # ------------------------------------------------------------------
    def _start_timer(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def _tick(self) -> None:
        now = time.perf_counter()
        if self._guide_active:
            self._guide_progress = min(1.0, self._guide_progress + FRAME_INTERVAL / GUIDE_GROW_DURATION)
            self._guide_alpha = min(1.0, self._guide_alpha + FRAME_INTERVAL / GUIDE_GROW_DURATION)
        else:
            self._guide_alpha = max(0.0, self._guide_alpha - FRAME_INTERVAL / FADE_DURATION)

        for particle in self._particles:
            particle.vx *= 0.96
            particle.vy *= 0.96
            particle.position.setX(particle.position.x() + particle.vx * FRAME_INTERVAL)
            particle.position.setY(particle.position.y() + particle.vy * FRAME_INTERVAL)
        self._particles = [p for p in self._particles if now - p.born <= p.life]
        self._strokes = [
            s for s in self._strokes if s.end_time is None or now - s.end_time <= FADE_DURATION
        ]
        self.update()

        if (
            not self._strokes
            and not self._particles
            and not self._guide_active
            and self._guide_alpha <= 0.01
        ):
            self._timer.stop()

    # ------------------------------------------------------------------
    def _spawn_particles(self, point: QPointF, now: float, style: str) -> None:
        colors = STYLES.get(style, STYLES["whiteOrange"]).particles
        for _ in range(random.randint(1, 3)):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(20, 90)
            self._particles.append(
                _Particle(
                    position=QPointF(point),
                    vx=math.cos(angle) * speed,
                    vy=math.sin(angle) * speed,
                    born=now,
                    life=random.uniform(0.35, 0.9),
                    size=random.uniform(1.5, 4.5),
                    color=random.choice(colors),
                )
            )

    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802 (Qt API)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        now = time.perf_counter()
        self._draw_particles(painter, now)
        self._draw_strokes(painter, now)
        self._draw_guides(painter)
        painter.end()

    def _draw_particles(self, painter: QPainter, now: float) -> None:
        painter.setPen(Qt.NoPen)
        for particle in self._particles:
            remaining = max(0.0, 1.0 - (now - particle.born) / particle.life)
            if remaining <= 0.01:
                continue
            radius = particle.size * (0.5 + 0.5 * remaining)
            rect = QRectF(
                particle.position.x() - radius,
                particle.position.y() - radius,
                radius * 2,
                radius * 2,
            )
            painter.setBrush(qcolor(particle.color, 0.20 * remaining))
            painter.drawEllipse(rect.adjusted(-2, -2, 2, 2))
            painter.setBrush(qcolor(particle.color, remaining))
            painter.drawEllipse(rect)

    def _draw_strokes(self, painter: QPainter, now: float) -> None:
        for stroke in self._strokes:
            alpha = 1.0
            if stroke.end_time is not None:
                alpha = max(0.0, 1.0 - (now - stroke.end_time) / FADE_DURATION)
            if alpha <= 0.01:
                continue
            colors = STYLES.get(stroke.style, STYLES["whiteOrange"])
            if len(stroke.points) <= 1:
                self._draw_dot(painter, stroke, alpha, colors)
                continue
            path = self._smooth_path(stroke.points)
            painter.setBrush(Qt.NoBrush)
            for width, factor in ((18.0, 0.10), (12.0, 0.18), (7.0, 0.38)):
                pen = QPen(qcolor(colors.glow, factor * alpha), width)
                pen.setCapStyle(Qt.RoundCap)
                pen.setJoinStyle(Qt.RoundJoin)
                painter.setPen(pen)
                painter.drawPath(path)
            pen = QPen(qcolor(colors.core, alpha), 2.2)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(path)

    def _draw_dot(self, painter: QPainter, stroke: _Stroke, alpha: float, colors: StyleColors) -> None:
        point = stroke.points[0]
        radius = 3.5
        painter.setPen(Qt.NoPen)
        painter.setBrush(qcolor(colors.glow, 0.7 * alpha))
        painter.drawEllipse(QRectF(point.x() - radius, point.y() - radius, radius * 2, radius * 2))
        painter.setBrush(qcolor(colors.core, alpha))
        painter.drawEllipse(
            QRectF(point.x() - radius + 1.5, point.y() - radius + 1.5, radius * 2 - 3, radius * 2 - 3)
        )

    def _draw_guides(self, painter: QPainter) -> None:
        if self._guide_alpha <= 0.01:
            return
        colors = STYLES.get(resolve_style(self._style), STYLES["whiteOrange"])
        center_y = self.height() / 2.0
        # Windows y grows down: the lines grow from the centre towards the top
        # and bottom edges of the screen.
        y_top = center_y + (0.0 - center_y) * self._guide_progress
        y_bottom = center_y + (self.height() - center_y) * self._guide_progress
        for x in (GUIDE_INSET, self.width() - GUIDE_INSET):
            painter.setBrush(Qt.NoBrush)
            pen = QPen(qcolor(colors.glow, 0.35 * self._guide_alpha), 9)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(x, y_top), QPointF(x, y_bottom))
            pen = QPen(qcolor(colors.core, self._guide_alpha), 2.0)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(x, y_top), QPointF(x, y_bottom))

    @staticmethod
    def _smooth_path(points: list[QPointF]) -> QPainterPath:
        path = QPainterPath()
        if not points:
            return path
        path.moveTo(points[0])
        if len(points) <= 2:
            path.lineTo(points[-1])
            return path
        for index in range(1, len(points) - 1):
            current = points[index]
            nxt = points[index + 1]
            mid = QPointF((current.x() + nxt.x()) / 2.0, (current.y() + nxt.y()) / 2.0)
            path.quadTo(current, mid)
        path.lineTo(points[-1])
        return path


class OverlayManager:
    def __init__(self) -> None:
        self.monitors: list[MonitorInfo] = []
        self.overlays: dict[str, OverlayWindow] = {}
        self._style = "whiteOrange"
        self.can_rebuild = None
        self._connected_screens: set[int] = set()
        self._refresh_timer = QTimer()
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self.rebuild)
        self.rebuild()
        app = QGuiApplication.instance()
        if app is not None:
            app.screenAdded.connect(lambda _screen: self._schedule_rebuild())
            app.screenRemoved.connect(lambda _screen: self._schedule_rebuild())

    def _schedule_rebuild(self) -> None:
        self._refresh_timer.start(300)

    @staticmethod
    def _normalise_device(name: str) -> str:
        return name.replace("\\\\.\\", "").upper()

    def _build_monitors(self) -> list[MonitorInfo]:
        physical = win32.get_monitors()
        result: list[MonitorInfo] = []
        used: set[int] = set()
        screens = QGuiApplication.screens()

        def rect_size(rect):
            return rect[2] - rect[0], rect[3] - rect[1]

        for index, screen in enumerate(screens):
            logical = screen.geometry()
            dpr = float(screen.devicePixelRatio() or 1.0)
            wanted_w = int(round(logical.width() * dpr))
            wanted_h = int(round(logical.height() * dpr))
            key = self._normalise_device(screen.name())

            info = None
            # 1) exact device or friendly monitor name
            for candidate in physical:
                if id(candidate) in used:
                    continue
                names = {
                    self._normalise_device(candidate.get("device", "")),
                    self._normalise_device(candidate.get("friendly", "")),
                }
                if key and key in names:
                    info = candidate
                    break

            # 2) match by physical size and position
            if info is None:
                size_matches = [
                    candidate
                    for candidate in physical
                    if id(candidate) not in used
                    and abs(rect_size(candidate["rect"])[0] - wanted_w) <= 2
                    and abs(rect_size(candidate["rect"])[1] - wanted_h) <= 2
                ]
                if len(size_matches) > 1:
                    # Prefer the monitor on the same side of the primary
                    # display (negative vs non-negative x).
                    want_negative = logical.x() < 0
                    side_matches = [
                        candidate
                        for candidate in size_matches
                        if (candidate["rect"][0] < 0) == want_negative
                    ]
                    if side_matches:
                        size_matches = side_matches
                if size_matches:
                    info = size_matches[0]

            # 3) last resort: first unused / index
            if info is None:
                remaining = [candidate for candidate in physical if id(candidate) not in used]
                if remaining:
                    info = remaining[0]
                elif index < len(physical):
                    info = physical[index]

            if info is None:
                left = int(logical.x() * dpr)
                top = int(logical.y() * dpr)
                device = screen.name()
                physical_rect = (left, top, left + wanted_w, top + wanted_h)
            else:
                used.add(id(info))
                device = info["device"]
                physical_rect = info["rect"]
            result.append(
                MonitorInfo(
                    device=device,
                    physical=physical_rect,
                    logical=QRectF(logical),
                    screen=screen,
                    dpr=dpr,
                )
            )
        return result

    def rebuild(self) -> None:
        if self.can_rebuild is not None:
            try:
                if not self.can_rebuild():
                    self._refresh_timer.start(500)
                    return
            except Exception:
                pass
        for overlay in self.overlays.values():
            overlay.close()
            overlay.deleteLater()
        self.overlays.clear()
        self.monitors = self._build_monitors()
        for monitor in self.monitors:
            overlay = OverlayWindow(monitor)
            overlay.set_style(self._style)
            key = self._normalise_device(monitor.device)
            self.overlays[key] = overlay
        for screen in QGuiApplication.screens():
            if id(screen) not in self._connected_screens:
                self._connected_screens.add(id(screen))
                screen.geometryChanged.connect(lambda _rect: self._schedule_rebuild())
        log.info(
            "Overlays rebuilt: %s",
            ", ".join(f"{m.device} {m.physical} dpr={m.dpr:g}" for m in self.monitors),
        )

    def all_overlays(self) -> list[OverlayWindow]:
        return list(self.overlays.values())

    def set_style(self, style: str) -> None:
        self._style = style
        for overlay in self.overlays.values():
            overlay.set_style(style)

    def _monitor_for_physical(self, x: int, y: int) -> MonitorInfo | None:
        for monitor in self.monitors:
            left, top, right, bottom = monitor.physical
            if left <= x <= right and top <= y <= bottom:
                return monitor
        info = win32.monitor_for_point(x, y)
        if info:
            key = self._normalise_device(info["device"])
            for monitor in self.monitors:
                if self._normalise_device(monitor.device) == key:
                    return monitor
        return self.monitors[0] if self.monitors else None

    def overlay_for_screen(self, screen) -> OverlayWindow | None:
        for monitor in self.monitors:
            if monitor.screen is screen:
                return self.overlays.get(self._normalise_device(monitor.device))
        return None

    def point_from_physical(self, x: int, y: int):
        """Return (monitor, overlay, local_point, logical_global_point)."""
        monitor = self._monitor_for_physical(x, y)
        if monitor is None:
            return None
        local_x = (float(x) - monitor.physical[0]) / monitor.dpr
        local_y = (float(y) - monitor.physical[1]) / monitor.dpr
        overlay = self.overlays.get(self._normalise_device(monitor.device))
        global_x = monitor.logical.x() + local_x
        global_y = monitor.logical.y() + local_y
        return monitor, overlay, (local_x, local_y), (global_x, global_y)

    def screen_for_logical_point(self, x: float, y: float):
        screen = QGuiApplication.screenAt(QPointF(x, y).toPoint())
        if screen is not None:
            return screen
        for monitor in self.monitors:
            if monitor.logical.contains(x, y):
                return monitor.screen
        return QGuiApplication.primaryScreen()

    def logical_rect_to_physical(self, rect: QRectF) -> tuple[int, int, int, int] | None:
        left = top = None
        right = bottom = None
        for monitor in self.monitors:
            intersection = monitor.logical.intersected(rect)
            if intersection.isEmpty():
                continue
            local_left = (intersection.left() - monitor.logical.left()) * monitor.dpr
            local_top = (intersection.top() - monitor.logical.top()) * monitor.dpr
            local_right = (intersection.right() - monitor.logical.left()) * monitor.dpr
            local_bottom = (intersection.bottom() - monitor.logical.top()) * monitor.dpr
            phys_left = int(monitor.physical[0] + local_left)
            phys_top = int(monitor.physical[1] + local_top)
            phys_right = int(monitor.physical[0] + local_right)
            phys_bottom = int(monitor.physical[1] + local_bottom)
            left = phys_left if left is None else min(left, phys_left)
            top = phys_top if top is None else min(top, phys_top)
            right = phys_right if right is None else max(right, phys_right)
            bottom = phys_bottom if bottom is None else max(bottom, phys_bottom)
        if left is None or top is None or right is None or bottom is None:
            return None
        return left, top, max(left + 1, right), max(top + 1, bottom)

    def hide_all(self) -> None:
        for overlay in self.overlays.values():
            overlay.hide()

    def show_all(self) -> None:
        for overlay in self.overlays.values():
            overlay.show()
            overlay.ensure_visible()

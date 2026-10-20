"""A small drawing canvas used for recording gestures in Settings."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import QWidget

from ..model.gestures import Strokes


class PatternCanvas(QWidget):
    changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.strokes: Strokes = []
        self._current: list[tuple[float, float]] = []
        self.setMinimumSize(220, 160)
        self.setMouseTracking(False)
        self.setCursor(Qt.CrossCursor)
        self.setFocusPolicy(Qt.StrongFocus)

    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        return QSize(220, 160)

    def clear(self) -> None:
        self.strokes = []
        self._current = []
        self.update()
        self.changed.emit()

    def set_strokes(self, strokes: Strokes) -> None:
        self.strokes = [[(float(x), float(y)) for x, y in stroke] for stroke in strokes]
        self._current = []
        self.update()
        self.changed.emit()

    def current_strokes(self) -> Strokes:
        result = list(self.strokes)
        if len(self._current) >= 2:
            result.append(list(self._current))
        return result

    # ------------------------------------------------------------------
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton:
            return
        point = event.position()
        self._current = [(point.x(), point.y())]
        self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if not self._current:
            return
        point = event.position()
        last_x, last_y = self._current[-1]
        if math.hypot(point.x() - last_x, point.y() - last_y) < 1.5:
            return
        self._current.append((point.x(), point.y()))
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton or not self._current:
            return
        if len(self._current) >= 2:
            self.strokes.append(self._current)
        self._current = []
        self.update()
        self.changed.emit()

    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        palette = self.palette()
        background = palette.color(QPalette.Base)
        if background.lightness() > 200:
            background = QColor(250, 250, 252)
        painter.setBrush(background)
        painter.setPen(QPen(QColor(128, 128, 138, 90), 1))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)

        pen = QPen(palette.color(QPalette.WindowText), 2.4)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        for stroke in self.strokes:
            self._draw_stroke(painter, stroke)
        if len(self._current) >= 1:
            self._draw_stroke(painter, self._current)

        if not self.strokes and not self._current:
            hint = QColor(palette.color(QPalette.WindowText))
            hint.setAlpha(90)
            painter.setPen(hint)
            painter.drawText(self.rect(), Qt.AlignCenter, "在这里按住鼠标左键绘制")
        painter.end()

    @staticmethod
    def _draw_stroke(painter: QPainter, stroke: list[tuple[float, float]]) -> None:
        if not stroke:
            return
        if len(stroke) == 1:
            painter.drawPoint(QPointF(stroke[0][0], stroke[0][1]))
            return
        path = QPainterPath()
        path.moveTo(stroke[0][0], stroke[0][1])
        for x, y in stroke[1:]:
            path.lineTo(x, y)
        painter.drawPath(path)

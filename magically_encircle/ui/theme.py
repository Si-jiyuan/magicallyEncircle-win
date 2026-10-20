"""Icons, previews and a small light/dark theme helper."""

from __future__ import annotations

import math
import os
import winreg
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QApplication

from ..config import APP_DIR
from ..gesture import geometry
from ..model.gestures import Strokes


def _icon_path() -> Path:
    candidates = [
        APP_DIR / "assets" / "icon.png",
        Path(__file__).resolve().parents[1] / "assets" / "icon.png",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


def app_icon() -> QIcon:
    path = _icon_path()
    if path.exists():
        return QIcon(str(path))
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setBrush(QColor(255, 140, 31))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(QRectF(2, 2, 60, 60), 14, 14)
    painter.setPen(QPen(QColor(255, 255, 255), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawLine(QPointF(20, 42), QPointF(32, 20))
    painter.drawLine(QPointF(32, 20), QPointF(44, 42))
    painter.end()
    return QIcon(pixmap)


def is_dark_mode() -> bool:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return int(value) == 0
    except OSError:
        return False


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setWindowIcon(app_icon())
    if not is_dark_mode():
        return
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(32, 32, 36))
    palette.setColor(QPalette.WindowText, QColor(236, 236, 240))
    palette.setColor(QPalette.Base, QColor(24, 24, 28))
    palette.setColor(QPalette.AlternateBase, QColor(42, 42, 48))
    palette.setColor(QPalette.ToolTipBase, QColor(48, 48, 54))
    palette.setColor(QPalette.ToolTipText, QColor(236, 236, 240))
    palette.setColor(QPalette.Text, QColor(236, 236, 240))
    palette.setColor(QPalette.Button, QColor(45, 45, 52))
    palette.setColor(QPalette.ButtonText, QColor(236, 236, 240))
    palette.setColor(QPalette.BrightText, QColor(255, 90, 90))
    palette.setColor(QPalette.Link, QColor(90, 170, 255))
    palette.setColor(QPalette.Highlight, QColor(70, 120, 220))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(130, 130, 140))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(130, 130, 140))
    app.setPalette(palette)


def preview_pixmap(strokes: Strokes, size: int = 64, color: QColor | None = None) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    if color is None:
        app = QApplication.instance()
        color = app.palette().color(QPalette.WindowText) if app is not None else QColor(80, 80, 80)
    valid = [stroke for stroke in strokes if len(stroke) >= 2]
    points = [point for stroke in valid for point in stroke]
    if not points:
        return pixmap

    min_x, min_y, width, height = geometry.bounding_box(points)
    content = max(1.0, size - 8.0)
    scale = content / max(width, height, 1.0)
    offset_x = (size - width * scale) / 2.0
    offset_y = (size - height * scale) / 2.0

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(color, 1.8)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    for stroke in valid:
        path = QPainterPath()
        for index, (x, y) in enumerate(stroke):
            point = QPointF(offset_x + (x - min_x) * scale, offset_y + (y - min_y) * scale)
            if index == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        painter.drawPath(path)
    painter.end()
    return pixmap

"""The recognition feedback HUD shown near the bottom of the screen."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from ..platform_support import win32


class HudWindow(QWidget):
    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
            | Qt.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.NoFocus)

        self._panel = QFrame(self)
        self._panel.setObjectName("hudPanel")
        self._panel.setStyleSheet(
            "#hudPanel {"
            "  background: rgba(28, 28, 32, 225);"
            "  border: 1px solid rgba(255, 255, 255, 38);"
            "  border-radius: 14px;"
            "}"
        )
        self._title = QLabel("")
        self._title.setStyleSheet("color: white; font-size: 15px; font-weight: 600;")
        self._detail = QLabel("")
        self._detail.setStyleSheet("color: rgba(255,255,255,190); font-size: 12px;")
        self._detail.setWordWrap(True)

        inner = QVBoxLayout(self._panel)
        inner.setContentsMargins(20, 12, 20, 12)
        inner.setSpacing(3)
        inner.addWidget(self._title)
        inner.addWidget(self._detail)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._panel)

        self._fade: QPropertyAnimation | None = None
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)
        self.hide()

    def _apply_native(self) -> None:
        try:
            win32.set_overlay_native_styles(int(self.winId()))
        except Exception:
            pass

    def show_message(self, title: str, detail: str = "", near: tuple[float, float] | None = None) -> None:
        if self._fade is not None:
            self._fade.stop()
        self._hide_timer.stop()
        self._title.setText(title)
        self._detail.setText(detail)
        self._detail.setVisible(bool(detail))
        self._panel.layout().activate()
        self.adjustSize()

        screen = None
        if near is not None:
            screen = QGuiApplication.screenAt(QPoint(int(near[0]), int(near[1])))
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        geometry = screen.availableGeometry() if screen else None
        if geometry is not None:
            x = geometry.x() + (geometry.width() - self.width()) // 2
            y = geometry.y() + geometry.height() - self.height() - 110
            self.move(x, y)
        else:
            self.move(100, 100)

        self.setWindowOpacity(0.0)
        self.show()
        self._apply_native()
        self.raise_()
        self._animate(1.0, 120)
        self._hide_timer.start(1400)

    def _animate(self, target: float, duration: int) -> None:
        animation = QPropertyAnimation(self, b"windowOpacity", self)
        animation.setDuration(duration)
        animation.setStartValue(self.windowOpacity())
        animation.setEndValue(target)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.start()
        self._fade = animation

    def _fade_out(self) -> None:
        animation = QPropertyAnimation(self, b"windowOpacity", self)
        animation.setDuration(250)
        animation.setStartValue(self.windowOpacity())
        animation.setEndValue(0.0)
        animation.finished.connect(self.hide)
        animation.start()
        self._fade = animation

    def hide_now(self) -> None:
        self._hide_timer.stop()
        self.hide()

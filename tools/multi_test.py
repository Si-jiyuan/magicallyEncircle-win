"""Test Alt double-tap multi-stroke drawing (two-stroke X)."""

from __future__ import annotations

import os
import sys
import threading
import time

os.environ["MAGICALLY_ENCIRCLE_TEST_INPUT"] = "1"
os.environ["MAGICALLY_ENCIRCLE_DRY_RUN"] = "1"
os.environ["MAGICALLY_ENCIRCLE_ALLOW_CAPTURE"] = "1"

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from magically_encircle.app import _setup_logging
from magically_encircle.config import Settings
from magically_encircle.controller import MagicController
from magically_encircle.platform_support import win32
from magically_encircle.ui.theme import apply_theme

VK_MENU = 0x12
KEYEVENTF_KEYUP = 0x0002
LEFTDOWN = 0x0002
LEFTUP = 0x0004


def key(vk: int, up: bool = False) -> None:
    item = win32.INPUT()
    item.type = 1
    item.ki = win32.KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if up else 0, 0, 0)
    win32.send_inputs([item])


def mouse(flags: int) -> None:
    item = win32.INPUT()
    item.type = 0
    item.mi = win32.MOUSEINPUT(0, 0, 0, flags, 0, 0)
    win32.send_inputs([item])


def move(x: int, y: int) -> None:
    # SetCursorPos is enough here; the hook only needs the move events, and in
    # test mode they are accepted.  Using absolute SendInput moves the cursor
    # as well but SetCursorPos is simpler for this multi-stroke test.
    win32.user32.SetCursorPos(x, y)
    time.sleep(0.03)


def stroke(points: list[tuple[int, int]]) -> None:
    move(*points[0])
    mouse(LEFTDOWN)
    for point in points[1:]:
        move(*point)
    mouse(LEFTUP)
    time.sleep(0.08)


def simulate() -> None:
    time.sleep(0.8)
    # first tap
    key(VK_MENU)
    time.sleep(0.05)
    key(VK_MENU, True)
    time.sleep(0.1)
    # second press held -> multi-stroke session
    key(VK_MENU)
    time.sleep(0.06)
    stroke([(500, 350), (600, 430), (700, 510), (800, 600)])
    stroke([(800, 350), (700, 430), (600, 510), (500, 600)])
    time.sleep(0.05)
    key(VK_MENU, True)


def main() -> int:
    _setup_logging(True)
    win32.set_dpi_awareness()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    settings = Settings()
    settings.draw_trigger = "altLeft"
    settings.multi_stroke_mode = "doublePress"
    controller = MagicController(app, settings)
    controller._desktop_timer.stop()
    threading.Thread(target=simulate, daemon=True).start()
    QTimer.singleShot(4000, lambda: app.exit(0))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

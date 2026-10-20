"""End-to-end drawing test using synthetic input.

Run with:
    set MAGICALLY_ENCIRCLE_TEST_INPUT=1
    python -m tools.draw_test

The test presses Alt, draws a Z with the left button, releases Alt, then
captures the screen.  The app log should contain "Recognised built-in undo".
Set DRAW_TRIGGER=middle to test the middle-button mode; set DRAW_OFFSET_X to
draw on another monitor.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

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

LEFTDOWN = 0x0002
LEFTUP = 0x0004
MIDDLEDOWN = 0x0020
MIDDLEUP = 0x0040
MOVE = 0x0001
ABSOLUTE = 0x8000
VIRTUALDESK = 0x4000
KEYUP = 0x0002
VK_MENU = 0x12


def mouse_event(flags: int) -> None:
    item = win32.INPUT()
    item.type = 0  # INPUT_MOUSE
    item.mi = win32.MOUSEINPUT(0, 0, 0, flags, 0, 0)
    win32.send_inputs([item])


def move_absolute(x: int, y: int) -> None:
    monitors = win32.get_monitors()
    left = min(m["rect"][0] for m in monitors)
    top = min(m["rect"][1] for m in monitors)
    right = max(m["rect"][2] for m in monitors)
    bottom = max(m["rect"][3] for m in monitors)
    width = max(1, right - left - 1)
    height = max(1, bottom - top - 1)
    nx = int(round((x - left) * 65535 / width))
    ny = int(round((y - top) * 65535 / height))
    item = win32.INPUT()
    item.type = 0
    item.mi = win32.MOUSEINPUT(
        nx, ny, 0, MOVE | ABSOLUTE | VIRTUALDESK, 0, 0
    )
    win32.send_inputs([item])


def key_event(vk: int, up: bool) -> None:
    item = win32.INPUT()
    item.type = 1  # INPUT_KEYBOARD
    item.ki = win32.KEYBDINPUT(vk, 0, KEYUP if up else 0, 0, 0)
    win32.send_inputs([item])


def simulate() -> None:
    time.sleep(0.8)
    middle = os.environ.get("DRAW_TRIGGER") == "middle"
    offset_x = int(os.environ.get("DRAW_OFFSET_X", "0"))
    if not middle:
        key_event(VK_MENU, False)
        time.sleep(0.08)
    move_absolute(500 + offset_x, 350)
    time.sleep(0.05)
    mouse_event(MIDDLEDOWN if middle else LEFTDOWN)
    points = [
        (500, 350), (560, 350), (620, 350), (680, 350), (740, 350),
        (800, 350), (820, 380), (760, 420), (700, 460), (640, 500),
        (580, 540), (520, 580), (500, 610), (560, 610), (620, 610),
        (680, 610), (740, 610), (800, 610), (840, 610),
    ]
    for x, y in points:
        move_absolute(x + offset_x, y)
        time.sleep(0.025)
    print("cursor before up", win32.get_cursor_pos(), flush=True)
    mouse_event(MIDDLEUP if middle else LEFTUP)
    print("cursor after up", win32.get_cursor_pos(), flush=True)
    time.sleep(0.05)
    if not middle:
        key_event(VK_MENU, True)


def main() -> int:
    _setup_logging(True)
    win32.set_dpi_awareness()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    settings = Settings()
    settings.draw_trigger = "middleButton" if os.environ.get("DRAW_TRIGGER") == "middle" else "altLeft"
    settings.multi_stroke_mode = "doublePress"
    settings.show_hud = True
    controller = MagicController(app, settings)
    threading.Thread(target=simulate, daemon=True).start()

    def grab() -> None:
        from PIL import ImageGrab

        image = ImageGrab.grab(all_screens=True)
        image.save(str(Path(tempfile.gettempdir()) / "draw_test.png"))
        print("grab saved", flush=True)

    QTimer.singleShot(1900, grab)
    QTimer.singleShot(5000, lambda: app.exit(0))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

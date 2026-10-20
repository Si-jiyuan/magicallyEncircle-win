"""Test global key capture for binding a custom gesture."""

from __future__ import annotations

import os
import sys
import threading
import time

os.environ["MAGICALLY_ENCIRCLE_TEST_INPUT"] = "1"
os.environ["MAGICALLY_ENCIRCLE_DRY_RUN"] = "1"

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from magically_encircle.app import _setup_logging
from magically_encircle.config import Settings
from magically_encircle.controller import MagicController
from magically_encircle.platform_support import win32
from magically_encircle.ui.theme import apply_theme

VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_K = 0x4B
KEYEVENTF_KEYUP = 0x0002


def key(vk: int, up: bool = False) -> None:
    item = win32.INPUT()
    item.type = 1
    item.ki = win32.KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if up else 0, 0, 0)
    win32.send_inputs([item])


def press() -> None:
    time.sleep(0.6)
    key(VK_CONTROL)
    key(VK_SHIFT)
    key(VK_K)
    time.sleep(0.05)
    key(VK_K, True)
    key(VK_SHIFT, True)
    key(VK_CONTROL, True)


def main() -> int:
    _setup_logging(True)
    win32.set_dpi_awareness()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    controller = MagicController(app, Settings())
    controller._desktop_timer.stop()
    gesture = __import__(
        "magically_encircle.model.gestures", fromlist=["CustomGesture"]
    ).CustomGesture.new("测试", [[(0, 0), (100, 100)]])
    controller.custom_gestures.append(gesture)
    controller.begin_key_capture(("custom", gesture.id))
    threading.Thread(target=press, daemon=True).start()

    def report() -> None:
        print(
            "bound:",
            gesture.key_code,
            hex(gesture.modifier_flags),
            gesture.key_display,
            "pending:",
            controller.pending_key_target,
            flush=True,
        )
        app.exit(0)

    QTimer.singleShot(1600, report)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

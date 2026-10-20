"""Exercise the dynamic tray menu construction."""

from __future__ import annotations

import os
import sys
import tempfile

os.environ["MAGICALLY_ENCIRCLE_DATA_DIR"] = tempfile.mkdtemp(prefix="magically-tray-")

from PySide6.QtWidgets import QApplication

from magically_encircle.config import Settings
from magically_encircle.controller import MagicController
from magically_encircle.model.gestures import CustomGesture
from magically_encircle.platform_support import win32
from magically_encircle.ui.theme import apply_theme
from magically_encircle.ui.tray import TrayController


def main() -> int:
    win32.set_dpi_awareness()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    controller = MagicController(app, Settings())
    controller._desktop_timer.stop()
    controller.custom_gestures.append(CustomGesture.new("测试", [[(0, 0), (50, 50)]]))
    controller.gesture_overrides["undo"] = [[[(0, 0), (30, 30)]]]
    tray = TrayController(controller, lambda: None)
    tray.rebuild()
    print("tray actions:", len(tray.menu.actions()), flush=True)
    for action in tray.menu.actions():
        print(" -", action.text(), "submenu" if action.menu() else "", flush=True)
    controller.shutdown()
    app.exit(0)
    print("tray test OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Regression test: toggling the controller on/off repeatedly."""

from __future__ import annotations

import os
import sys
import tempfile

os.environ["MAGICALLY_ENCIRCLE_DATA_DIR"] = tempfile.mkdtemp(prefix="magically-toggle-")

from PySide6.QtWidgets import QApplication

from magically_encircle.config import Settings
from magically_encircle.controller import MagicController
from magically_encircle.platform_support import win32
from magically_encircle.ui.theme import apply_theme


def main() -> int:
    win32.set_dpi_awareness()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    settings = Settings()
    controller = MagicController(app, settings)
    controller._desktop_timer.stop()
    for _ in range(3):
        controller.set_enabled(False)
        controller.set_enabled(True)
    controller.set_enabled(False)
    print("enabled:", controller.settings.enabled, "player:", controller.player._timer.isActive(), flush=True)
    assert controller.settings.enabled is False
    controller.set_enabled(True)
    controller.shutdown()
    app.exit(0)
    print("toggle test OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

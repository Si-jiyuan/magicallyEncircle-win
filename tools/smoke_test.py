"""Small startup smoke test (creates the UI and exits after a few seconds)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from magically_encircle.config import Settings
from magically_encircle.controller import MagicController
from magically_encircle.platform_support import win32
from magically_encircle.ui.settings import SettingsWindow
from magically_encircle.ui.theme import apply_theme
from magically_encircle.ui.tray import TrayController

OUT = Path(tempfile.gettempdir())


def main() -> int:
    win32.set_dpi_awareness()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    settings = Settings()
    controller = MagicController(app, settings)
    window = SettingsWindow(controller)
    window.show_and_raise()
    print("settings geometry", window.geometry(), window.isVisible(), flush=True)
    tray = TrayController(controller, window.show_and_raise)

    def grab() -> None:
        window.grab().save(str(OUT / "settings_widget.png"))
        print("window grab saved", flush=True)

    QTimer.singleShot(1200, grab)
    QTimer.singleShot(4000, lambda: app.exit(0))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

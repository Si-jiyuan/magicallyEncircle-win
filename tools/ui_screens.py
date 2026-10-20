"""Capture each Settings section to a PNG for visual inspection."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QScrollArea

from magically_encircle.config import Settings
from magically_encircle.controller import MagicController
from magically_encircle.model.gestures import CustomGesture
from magically_encircle.platform_support import win32
from magically_encircle.ui.settings import SettingsWindow
from magically_encircle.ui.theme import apply_theme

OUT = Path(tempfile.gettempdir())


def main() -> int:
    win32.set_dpi_awareness()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    controller = MagicController(app, Settings())
    controller._desktop_timer.stop()

    demo = CustomGesture.new("circle-copy", [[(20, 40), (60, 20), (90, 50), (70, 90), (30, 80), (20, 40)]])
    demo.key_code = 0x43
    demo.modifier_flags = 2
    demo.key_display = "Ctrl+C"
    demo2 = CustomGesture.new("open-browser", [[(20, 30), (80, 30), (80, 80), (20, 80)]])
    demo2.key_code = None
    demo2.app_paths = [r"C:\Program Files\Google\Chrome\Application\chrome.exe"]
    controller.custom_gestures.extend([demo, demo2])

    window = SettingsWindow(controller)
    window.show_and_raise()
    window.move(100, 100)

    def capture(index: int) -> None:
        window.sidebar.setCurrentRow(index)
        app.processEvents()
        window.grab().save(str(OUT / f"ui_section_{index}.png"))
        print("saved", index, flush=True)

    for index in range(5):
        QTimer.singleShot(300 + index * 250, lambda i=index: capture(i))

    def capture_bottom() -> None:
        window.sidebar.setCurrentRow(0)
        general = window.sections[0][1]
        scroll = general.findChild(QScrollArea)
        if scroll is not None:
            scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
        app.processEvents()
        window.grab().save(str(OUT / "settings_general_bottom.png"))
        print("saved general bottom", flush=True)

    def capture_coffee() -> None:
        general = window.sections[0][1]
        general._show_coffee()
        app.processEvents()
        popup = getattr(general, "_coffee_popup", None)
        if popup is not None:
            popup.grab().save(str(OUT / "coffee.png"))
            popup.hide()
        print("saved coffee popup", flush=True)

    QTimer.singleShot(1700, capture_bottom)
    QTimer.singleShot(1900, capture_coffee)
    QTimer.singleShot(2400, lambda: app.exit(0))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

"""Application entry point."""

from __future__ import annotations

import logging
import logging.handlers
import sys
import traceback

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from .config import APP_NAME, DATA_DIR, LOG_DIR, SETTINGS_FILE, Settings
from .constants import APP_MUTEX
from .platform_support import win32


def _setup_logging(debug: bool) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    level = logging.DEBUG if debug else logging.INFO
    root = logging.getLogger()
    root.setLevel(level)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "app.log", maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
    if debug and sys.stderr is not None:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root.addHandler(console)


def _install_excepthook() -> None:
    def hook(exc_type, exc_value, exc_tb):
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logging.getLogger(__name__).critical("Unhandled exception:\n%s", text)
        # Also keep a crash file in case the logging handler itself failed.
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with (LOG_DIR / "crash.log").open("a", encoding="utf-8") as handle:
                handle.write(text)
                handle.write("\n")
        except Exception:
            pass
        try:
            QMessageBox.critical(
                None,
                "magicallyEncircle 出错",
                f"{exc_type.__name__}: {exc_value}\n\n详细日志：{LOG_DIR / 'app.log'}",
            )
        except Exception:
            pass

    sys.excepthook = hook


def main() -> int:
    debug = "--debug" in sys.argv
    win32.set_dpi_awareness()

    # Check the single-instance mutex before touching the log file.  A second
    # instance must not open the same rotating log while the first one runs.
    mutex, already_running = win32.create_single_instance_mutex(APP_MUTEX)
    if already_running:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        app = QApplication(sys.argv)
        QMessageBox.information(None, APP_NAME, "magicallyEncircle 已经在运行。")
        return 0

    _setup_logging(debug)
    log = logging.getLogger(__name__)
    log.info("Starting magicallyEncircle (data: %s)", DATA_DIR)

    if "--self-test" in sys.argv:
        from PIL import Image, ImageDraw

        from .platform_support import ocr

        log.info("monitors: %s", win32.get_monitors())
        image = Image.new("RGB", (600, 200), "white")
        drawer = ImageDraw.Draw(image)
        drawer.text((30, 70), "Hello Windows OCR 12345", fill="black")
        log.info("OCR available: %s", ocr.available())
        log.info("OCR result: %r", ocr.recognize(image))
        log.info("Self-test finished")
        return 0

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    _install_excepthook()

    from .ui.theme import apply_theme

    apply_theme(app)

    from .controller import MagicController
    from .ui.settings import SettingsWindow
    from .ui.tray import TrayController

    settings = Settings()
    first_run = not SETTINGS_FILE.exists()
    try:
        from .platform_support import autostart

        settings.launch_at_login = autostart.is_enabled()
    except Exception:
        pass
    controller = MagicController(app, settings)
    window = SettingsWindow(controller)
    tray = TrayController(controller, window.show_and_raise)
    app.aboutToQuit.connect(controller.shutdown)
    if first_run or "--autostart" not in sys.argv:
        tray.show_startup_hint()
    if "--settings" in sys.argv or not QSystemTrayIcon.isSystemTrayAvailable():
        window.show_and_raise()

    # Keep references alive for the lifetime of the event loop.
    app._magically_controller = controller  # type: ignore[attr-defined]
    app._magically_window = window  # type: ignore[attr-defined]
    app._magically_tray = tray  # type: ignore[attr-defined]
    app._magically_mutex = mutex  # type: ignore[attr-defined]

    if "--autostart" not in sys.argv:
        log.info("Running in tray; use the tray icon to open Settings")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

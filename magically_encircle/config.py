"""Paths, portable-mode handling and JSON settings."""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from .constants import (
    APP_NAME,
    CLOSE_WINDOW,
    MULTI_DOUBLE_PRESS,
    TRIGGER_ALT_LEFT,
)

log = logging.getLogger(__name__)


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


APP_DIR = _app_dir()
PORTABLE = (APP_DIR / "portable.flag").exists() or "--portable" in sys.argv


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _choose_data_dir() -> Path:
    override = os.environ.get("MAGICALLY_ENCIRCLE_DATA_DIR")
    if override:
        path = Path(override)
        if _writable(path):
            return path
    candidates: list[Path] = []
    if PORTABLE:
        candidates.append(APP_DIR / "data")
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / APP_NAME)
    candidates.append(Path.home() / f".{APP_NAME}")
    for candidate in candidates:
        if _writable(candidate):
            return candidate
    return Path(tempfile.gettempdir()) / APP_NAME


DATA_DIR = _choose_data_dir()
LOG_DIR = DATA_DIR / "logs"
SETTINGS_FILE = DATA_DIR / "settings.json"
GESTURES_FILE = DATA_DIR / "gestures.json"
OVERRIDES_FILE = DATA_DIR / "builtin_overrides.json"
BUILTIN_SHORTCUTS_FILE = DATA_DIR / "builtin_shortcuts.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "enabled": True,
    "showRecognitionHUD": True,
    "style": "whiteOrange",
    "drawTrigger": TRIGGER_ALT_LEFT,
    "multiStrokeMode": MULTI_DOUBLE_PRESS,
    "middleRecognitionSpeed": "normal",
    "closeAction": CLOSE_WINDOW,
    "playbackSpeed": 0.5,
    "launchAtLogin": False,
    "autoCheckUpdates": False,
}


def atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON via a temporary file so a crash cannot truncate the data."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass


def read_json(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default
    except (OSError, ValueError) as exc:
        log.warning("Could not read %s: %s", path, exc)
        return default


class Settings:
    """Small typed wrapper around settings.json."""

    def __init__(self) -> None:
        self.data: dict[str, Any] = dict(DEFAULT_SETTINGS)
        loaded = read_json(SETTINGS_FILE, {})
        if isinstance(loaded, dict):
            for key, value in loaded.items():
                if key in DEFAULT_SETTINGS and isinstance(value, type(DEFAULT_SETTINGS[key])):
                    self.data[key] = value
                elif key in DEFAULT_SETTINGS and DEFAULT_SETTINGS[key] is None:
                    self.data[key] = value

    def save(self) -> None:
        atomic_write_json(SETTINGS_FILE, self.data)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        if self.data.get(key) != value:
            self.data[key] = value
            self.save()

    # Convenience properties -------------------------------------------------
    @property
    def enabled(self) -> bool:
        return bool(self.data["enabled"])

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self.set("enabled", bool(value))

    @property
    def show_hud(self) -> bool:
        return bool(self.data["showRecognitionHUD"])

    @show_hud.setter
    def show_hud(self, value: bool) -> None:
        self.set("showRecognitionHUD", bool(value))

    @property
    def style(self) -> str:
        return str(self.data["style"])

    @style.setter
    def style(self, value: str) -> None:
        self.set("style", value)

    @property
    def draw_trigger(self) -> str:
        return str(self.data["drawTrigger"])

    @draw_trigger.setter
    def draw_trigger(self, value: str) -> None:
        self.set("drawTrigger", value)

    @property
    def multi_stroke_mode(self) -> str:
        return str(self.data["multiStrokeMode"])

    @multi_stroke_mode.setter
    def multi_stroke_mode(self, value: str) -> None:
        self.set("multiStrokeMode", value)

    @property
    def middle_speed(self) -> str:
        return str(self.data["middleRecognitionSpeed"])

    @middle_speed.setter
    def middle_speed(self, value: str) -> None:
        self.set("middleRecognitionSpeed", value)

    @property
    def close_action(self) -> str:
        return str(self.data["closeAction"])

    @close_action.setter
    def close_action(self, value: str) -> None:
        self.set("closeAction", value)

    @property
    def playback_speed(self) -> float:
        return float(self.data["playbackSpeed"])

    @playback_speed.setter
    def playback_speed(self, value: float) -> None:
        self.set("playbackSpeed", float(value))

    @property
    def launch_at_login(self) -> bool:
        return bool(self.data["launchAtLogin"])

    @launch_at_login.setter
    def launch_at_login(self, value: bool) -> None:
        self.set("launchAtLogin", bool(value))

    @property
    def auto_check_updates(self) -> bool:
        return bool(self.data["autoCheckUpdates"])

    @auto_check_updates.setter
    def auto_check_updates(self, value: bool) -> None:
        self.set("autoCheckUpdates", bool(value))

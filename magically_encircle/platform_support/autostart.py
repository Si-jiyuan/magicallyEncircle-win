"""Start-at-login support via the per-user Run registry key."""

from __future__ import annotations

import logging
import os
import sys
import winreg
from pathlib import Path

from ..config import APP_DIR

log = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "magicallyEncircle"


def _command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}" --autostart'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    executable = pythonw if pythonw.exists() else Path(sys.executable)
    entry = APP_DIR / "run_app.py"
    return f'"{executable}" "{entry}" --autostart'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return str(value).strip().lower() == _command().strip().lower()
    except FileNotFoundError:
        return False
    except OSError:
        log.exception("Could not read the Run registry key")
        return False


def set_enabled(enabled: bool) -> bool:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _command())
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        log.exception("Could not update the Run registry key")
        return False

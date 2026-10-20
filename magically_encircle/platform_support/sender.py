"""Sending keyboard shortcuts and launching applications."""

from __future__ import annotations

import logging
import os
import threading
import time

from ..constants import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_SHIFT,
    MOD_WIN,
    VK_CONTROL,
    VK_LWIN,
    VK_MENU,
    VK_RIGHT,
    VK_LEFT,
    VK_UP,
    VK_DOWN,
    VK_HOME,
    VK_END,
    VK_PRIOR,
    VK_NEXT,
    VK_INSERT,
    VK_DELETE,
    VK_SNAPSHOT,
)
from . import win32

log = logging.getLogger(__name__)

DRY_RUN = os.environ.get("MAGICALLY_ENCIRCLE_DRY_RUN") == "1"

MODIFIER_KEYS = [
    (MOD_CONTROL, VK_CONTROL),
    (MOD_ALT, VK_MENU),
    (MOD_SHIFT, 0x10),
    (MOD_WIN, VK_LWIN),
]

EXTENDED_KEYS = {
    VK_LEFT,
    VK_RIGHT,
    VK_UP,
    VK_DOWN,
    VK_HOME,
    VK_END,
    VK_PRIOR,
    VK_NEXT,
    VK_INSERT,
    VK_DELETE,
    VK_SNAPSHOT,
    0x6F,  # numpad divide
    0x90,  # numlock
}

_action_lock = threading.Lock()


def modifiers_held() -> int:
    return win32.modifiers_from_state()


def wait_for_modifiers_released(timeout: float = 0.6) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if win32.modifiers_from_state() == 0:
            return
        time.sleep(0.03)


def _keystroke(vk: int, modifiers: int = 0) -> None:
    wait_for_modifiers_released()
    extended = vk in EXTENDED_KEYS
    active = [(flag, key) for flag, key in MODIFIER_KEYS if modifiers & flag]

    down_events = [win32.key_input(modifier_vk, False) for _flag, modifier_vk in active]
    if down_events:
        win32.send_inputs(down_events)
        time.sleep(0.02)

    key_events = [
        win32.key_input(vk, False, extended=extended),
        win32.key_input(vk, True, extended=extended),
    ]
    sent = win32.send_inputs(key_events)
    if sent != len(key_events):
        log.warning(
            "SendInput sent %s/%s key events (error %s)",
            sent,
            len(key_events),
            __import__("ctypes").get_last_error(),
        )
    if active:
        time.sleep(0.02)
        up_events = [win32.key_input(modifier_vk, True) for _flag, modifier_vk in reversed(active)]
        win32.send_inputs(up_events)


def send_shortcut(vk: int, modifiers: int = 0, *, async_: bool = True) -> None:
    """Send a shortcut.  The default runs in a daemon thread so the Qt main
    thread is never blocked while waiting for the user to release Alt."""

    if DRY_RUN:
        log.info("DRY RUN shortcut vk=0x%02X modifiers=0x%X", vk, modifiers)
        return

    def run() -> None:
        with _action_lock:
            try:
                _keystroke(vk, modifiers)
            except Exception:
                log.exception("Could not send shortcut")

    if async_:
        threading.Thread(target=run, name="SendShortcut", daemon=True).start()
    else:
        run()


def send_shortcuts(shortcuts: list[tuple[int, int]], interval: float = 0.2) -> None:
    def run() -> None:
        with _action_lock:
            wait_for_modifiers_released()
            for index, (vk, modifiers) in enumerate(shortcuts):
                if index:
                    time.sleep(interval)
                try:
                    _keystroke(vk, modifiers)
                except Exception:
                    log.exception("Could not send shortcut sequence")

    threading.Thread(target=run, name="SendShortcutSequence", daemon=True).start()


def lock_screen() -> None:
    if DRY_RUN:
        log.info("DRY RUN LockWorkStation")
        return
    try:
        win32.lock_workstation()
    except Exception:
        log.exception("LockWorkStation failed")


def open_path(path: str) -> bool:
    """Open an executable/document, activating an existing window if possible."""
    if DRY_RUN:
        log.info("DRY RUN open %s", path)
        return True
    try:
        if path.lower().endswith(".exe") and os.path.exists(path):
            if win32.activate_window_for_path(path):
                return True
        return win32.shell_execute(path)
    except Exception:
        log.exception("Could not open %s", path)
        return False


def open_paths(paths: list[str]) -> tuple[list[str], list[str]]:
    opened: list[str] = []
    missing: list[str] = []
    for path in paths:
        if not os.path.exists(path) and not path.startswith("shell:"):
            missing.append(path)
            continue
        if open_path(path):
            opened.append(path)
        else:
            missing.append(path)
    return opened, missing

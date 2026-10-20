from __future__ import annotations

import ctypes
import sys

from magically_encircle.platform_support import win32

pid = int(sys.argv[1]) if len(sys.argv) > 1 else None


@ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
def callback(hwnd, _):
    window_pid = ctypes.c_ulong()
    win32.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
    if pid is not None and window_pid.value != pid:
        return True
    length = win32.user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    win32.user32.GetWindowTextW(hwnd, buffer, length + 1)
    rect = win32.RECT()
    win32.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    visible = bool(win32.user32.IsWindowVisible(hwnd))
    print(
        f"hwnd={int(hwnd)} pid={window_pid.value} visible={visible} "
        f"rect=({rect.left},{rect.top},{rect.right},{rect.bottom}) title={buffer.value!r}"
    )
    return True


win32.user32.EnumWindows(callback, 0)

"""Thin ctypes bindings for the Win32 APIs used by the app.

Keeping the prototypes in one place makes the rest of the code readable and
avoids 64-bit pointer truncation bugs.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from typing import Iterable

from ..constants import (
    GWL_EXSTYLE,
    HWND_TOPMOST,
    KEY_NAMES,
    MOD_ALT,
    MOD_CONTROL,
    MOD_SHIFT,
    MOD_WIN,
    SWP_NOACTIVATE,
    SWP_NOMOVE,
    SWP_NOSIZE,
    SWP_SHOWWINDOW,
    VK_CONTROL,
    VK_LWIN,
    VK_MENU,
    VK_RWIN,
    VK_SHIFT,
    WDA_EXCLUDEFROMCAPTURE,
    WS_EX_LAYERED,
    WS_EX_NOACTIVATE,
    WS_EX_TOOLWINDOW,
    WS_EX_TRANSPARENT,
)

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
ULONG_PTR = ctypes.c_size_t
HHOOK = ctypes.c_void_p
HMONITOR = ctypes.c_void_p

WM_QUIT = 0x0012


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT),
    ]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),
    ]


class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("DeviceName", wintypes.WCHAR * 32),
        ("DeviceString", wintypes.WCHAR * 128),
        ("StateFlags", wintypes.DWORD),
        ("DeviceID", wintypes.WCHAR * 128),
        ("DeviceKey", wintypes.WCHAR * 128),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", INPUT_UNION)]


MOUSEHOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
KEYHOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
MONITORENUMPROC = ctypes.WINFUNCTYPE(
    wintypes.BOOL, HMONITOR, wintypes.HDC, ctypes.POINTER(RECT), wintypes.LPARAM
)

# ---------------------------------------------------------------------------
# Prototypes
# ---------------------------------------------------------------------------

user32.SetWindowsHookExW.argtypes = [ctypes.c_int, ctypes.c_void_p, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = HHOOK
user32.UnhookWindowsHookEx.argtypes = [HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.CallNextHookEx.argtypes = [HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = wintypes.SHORT
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.SetWindowPos.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.LockWorkStation.argtypes = []
user32.LockWorkStation.restype = wintypes.BOOL
user32.GetKeyNameTextW.argtypes = [wintypes.LONG, wintypes.LPWSTR, ctypes.c_int]
user32.GetKeyNameTextW.restype = ctypes.c_int
user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
user32.MapVirtualKeyW.restype = wintypes.UINT
user32.MonitorFromPoint.argtypes = [POINT, wintypes.DWORD]
user32.MonitorFromPoint.restype = HMONITOR
user32.GetMonitorInfoW.argtypes = [HMONITOR, ctypes.POINTER(MONITORINFOEXW)]
user32.GetMonitorInfoW.restype = wintypes.BOOL
user32.EnumDisplayMonitors.argtypes = [
    wintypes.HDC,
    ctypes.POINTER(RECT),
    MONITORENUMPROC,
    wintypes.LPARAM,
]
user32.EnumDisplayMonitors.restype = wintypes.BOOL
user32.EnumDisplayDevicesW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.POINTER(DISPLAY_DEVICEW),
    wintypes.DWORD,
]
user32.EnumDisplayDevicesW.restype = wintypes.BOOL
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
if hasattr(user32, "SetProcessDpiAwarenessContext"):
    user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE

shell32.ShellExecuteW.argtypes = [
    wintypes.HWND,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    ctypes.c_int,
]
shell32.ShellExecuteW.restype = wintypes.HINSTANCE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def set_dpi_awareness() -> None:
    """Enable per-monitor v2 DPI awareness before Qt is imported/created."""
    try:
        if hasattr(user32, "SetProcessDpiAwarenessContext"):
            if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
                return
    except Exception:
        pass
    try:
        shcore = ctypes.WinDLL("shcore")
        shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass


def is_key_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def modifiers_from_state() -> int:
    modifiers = 0
    if is_key_down(VK_CONTROL):
        modifiers |= MOD_CONTROL
    if is_key_down(VK_MENU):
        modifiers |= MOD_ALT
    if is_key_down(VK_SHIFT):
        modifiers |= MOD_SHIFT
    if is_key_down(VK_LWIN) or is_key_down(VK_RWIN):
        modifiers |= MOD_WIN
    return modifiers


def get_cursor_pos() -> tuple[int, int]:
    point = POINT()
    if user32.GetCursorPos(ctypes.byref(point)):
        return point.x, point.y
    return 0, 0


def get_monitors() -> list[dict]:
    monitors: list[dict] = []

    def callback(hmonitor, hdc, rect_ptr, data):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            monitors.append(
                {
                    "handle": int(hmonitor or 0),
                    "device": info.szDevice,
                    "friendly": display_friendly_name(info.szDevice),
                    "rect": (
                        info.rcMonitor.left,
                        info.rcMonitor.top,
                        info.rcMonitor.right,
                        info.rcMonitor.bottom,
                    ),
                    "work": (
                        info.rcWork.left,
                        info.rcWork.top,
                        info.rcWork.right,
                        info.rcWork.bottom,
                    ),
                    "primary": bool(info.dwFlags & 1),
                }
            )
        return True

    callback_ref = MONITORENUMPROC(callback)
    user32.EnumDisplayMonitors(None, None, callback_ref, 0)
    return monitors


def display_friendly_name(device: str) -> str:
    """Return the EDID/monitor name (e.g. 'PHL 252M1RPE').

    Qt's QScreen.name() reports the device name for the primary monitor but
    usually the friendly monitor name for the others, so we need both.
    """
    try:
        display = DISPLAY_DEVICEW()
        display.cb = ctypes.sizeof(DISPLAY_DEVICEW)
        if user32.EnumDisplayDevicesW(device, 0, ctypes.byref(display), 0):
            return display.DeviceString
    except Exception:
        pass
    return ""


def monitor_for_point(x: int, y: int) -> dict | None:
    handle = user32.MonitorFromPoint(POINT(int(x), int(y)), 2)
    if not handle:
        return None
    info = MONITORINFOEXW()
    info.cbSize = ctypes.sizeof(MONITORINFOEXW)
    if not user32.GetMonitorInfoW(handle, ctypes.byref(info)):
        return None
    return {
        "handle": int(handle),
        "device": info.szDevice,
        "rect": (info.rcMonitor.left, info.rcMonitor.top, info.rcMonitor.right, info.rcMonitor.bottom),
        "work": (info.rcWork.left, info.rcWork.top, info.rcWork.right, info.rcWork.bottom),
        "primary": bool(info.dwFlags & 1),
    }


def set_overlay_native_styles(hwnd: int) -> None:
    try:
        ex_style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        ex_style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex_style)
        user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )
        user32.ShowWindow(hwnd, 4)  # SW_SHOWNOACTIVATE
        if os.environ.get("MAGICALLY_ENCIRCLE_ALLOW_CAPTURE") != "1":
            if not user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE):
                user32.SetWindowDisplayAffinity(hwnd, 0)
    except Exception:
        pass


def set_topmost(hwnd: int) -> None:
    try:
        user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )
    except Exception:
        pass


def display_affinity(hwnd: int, enabled: bool = True) -> None:
    try:
        user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE if enabled else 0)
    except Exception:
        pass


def vk_name(vk: int) -> str:
    if 0x41 <= vk <= 0x5A:
        return chr(vk)
    if 0x30 <= vk <= 0x39:
        return chr(vk)
    if vk in KEY_NAMES:
        return KEY_NAMES[vk]
    # Ask the keyboard layout for a localised name.  The high word of the
    # lParam passed to GetKeyNameText is the scan code.
    try:
        scan = user32.MapVirtualKeyW(vk, 0)
        if scan:
            buffer = ctypes.create_unicode_buffer(64)
            if user32.GetKeyNameTextW(scan << 16, buffer, 64):
                return buffer.value
    except Exception:
        pass
    return f"VK{vk:02X}"


def modifiers_display(modifiers: int) -> str:
    parts = []
    if modifiers & MOD_CONTROL:
        parts.append("Ctrl")
    if modifiers & MOD_ALT:
        parts.append("Alt")
    if modifiers & MOD_SHIFT:
        parts.append("Shift")
    if modifiers & MOD_WIN:
        parts.append("Win")
    return "+".join(parts)


def shortcut_display(vk: int, modifiers: int) -> str:
    prefix = modifiers_display(modifiers)
    name = vk_name(vk)
    return f"{prefix}+{name}" if prefix else name


def key_input(vk: int, key_up: bool, extended: bool = False) -> INPUT:
    flags = 0
    if key_up:
        flags |= 0x0002  # KEYEVENTF_KEYUP
    if extended:
        flags |= 0x0001  # KEYEVENTF_EXTENDEDKEY
    item = INPUT()
    item.type = 1  # INPUT_KEYBOARD
    item.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0)
    return item


def send_inputs(inputs: Iterable[INPUT]) -> int:
    items = list(inputs)
    if not items:
        return 0
    array = (INPUT * len(items))(*items)
    return int(user32.SendInput(len(items), array, ctypes.sizeof(INPUT)))


def shell_execute(path: str) -> bool:
    result = shell32.ShellExecuteW(None, "open", path, None, None, 1)
    return int(result or 0) > 32


def lock_workstation() -> bool:
    return bool(user32.LockWorkStation())


def _process_path(pid: int) -> str | None:
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        size = wintypes.DWORD(1024)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return buffer.value
    finally:
        kernel32.CloseHandle(handle)
    return None


def activate_window_for_path(path: str) -> bool:
    """Best-effort activation of an already-running executable."""
    target = os.path.normcase(os.path.abspath(path))
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return True
        exe = _process_path(pid.value)
        if exe and os.path.normcase(os.path.abspath(exe)) == target:
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(callback, 0)
    if found:
        user32.ShowWindow(found[0], 9)  # SW_RESTORE
        user32.SetForegroundWindow(found[0])
        return True
    return False


def visible_window_count(pid: int | None = None) -> int:
    count = 0

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        nonlocal count
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        if pid is not None:
            window_pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
            if window_pid.value != pid:
                return True
            count += 1
        else:
            count += 1
        return True

    user32.EnumWindows(callback, 0)
    return count


def create_single_instance_mutex(name: str):
    handle = kernel32.CreateMutexW(None, False, name)
    if not handle:
        return None, False
    already_exists = ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS
    return handle, already_exists

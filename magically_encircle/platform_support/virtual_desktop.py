"""Optional Windows virtual-desktop detection.

A topmost overlay window belongs to the virtual desktop it was created on.
After the user switches desktops the overlay is usually not visible anymore,
so the controller rebuilds the overlays when this COM interface reports that
they are on another desktop.  All failures are non-fatal.
"""

from __future__ import annotations

import ctypes
import logging
import uuid
from ctypes import wintypes

log = logging.getLogger(__name__)

ole32 = ctypes.WinDLL("ole32", use_last_error=True)

CLSCTX_INPROC_SERVER = 1
COINIT_APARTMENTTHREADED = 2
S_OK = 0


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid(value: str) -> GUID:
    parsed = uuid.UUID(value)
    guid = GUID()
    guid.Data1 = parsed.time_low
    guid.Data2 = parsed.time_mid
    guid.Data3 = parsed.time_hi_version
    for index, byte in enumerate(parsed.bytes[8:]):
        guid.Data4[index] = byte
    return guid


CLSID_VIRTUAL_DESKTOP_MANAGER = _guid("AA509086-5CA9-4C25-8F95-589D3C07B48A")
IID_IVIRTUAL_DESKTOP_MANAGER = _guid("A5CD92FF-29BE-454C-8D04-D82879FB3F1B")

ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
ole32.CoInitializeEx.restype = ctypes.c_long
ole32.CoCreateInstance.argtypes = [
    ctypes.POINTER(GUID),
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(GUID),
    ctypes.POINTER(ctypes.c_void_p),
]
ole32.CoCreateInstance.restype = ctypes.c_long

_manager: ctypes.c_void_p | None = None
_initialised = False
_failed = False


def _ensure_manager() -> ctypes.c_void_p | None:
    global _manager, _initialised, _failed
    if _manager is not None or _failed:
        return _manager
    if not _initialised:
        _initialised = True
        try:
            result = ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
            # S_FALSE is fine; RPC_E_CHANGED_MODE means another apartment mode
            # was already selected, which is also fine for this interface.
            if result not in (0, 1, -2147417850):  # S_OK, S_FALSE, RPC_E_CHANGED_MODE
                log.debug("CoInitializeEx returned 0x%08X", result & 0xFFFFFFFF)
        except Exception:
            log.debug("CoInitializeEx failed", exc_info=True)
    try:
        pointer = ctypes.c_void_p()
        hr = ole32.CoCreateInstance(
            ctypes.byref(CLSID_VIRTUAL_DESKTOP_MANAGER),
            None,
            CLSCTX_INPROC_SERVER,
            ctypes.byref(IID_IVIRTUAL_DESKTOP_MANAGER),
            ctypes.byref(pointer),
        )
        if hr != S_OK or not pointer.value:
            log.debug("VirtualDesktopManager unavailable (hr=0x%08X)", hr & 0xFFFFFFFF)
            _failed = True
            return None
        _manager = pointer
        log.info("VirtualDesktopManager available")
        return _manager
    except Exception:
        log.debug("VirtualDesktopManager creation failed", exc_info=True)
        _failed = True
        return None


def is_window_on_current_desktop(hwnd: int) -> bool | None:
    manager = _ensure_manager()
    if manager is None:
        return None
    try:
        vtable = ctypes.cast(
            manager, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        function = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, wintypes.HWND, ctypes.POINTER(wintypes.BOOL)
        )(vtable[3])
        on_current = wintypes.BOOL()
        hr = function(manager, hwnd, ctypes.byref(on_current))
        if hr != S_OK:
            return None
        return bool(on_current.value)
    except Exception:
        log.debug("IsWindowOnCurrentVirtualDesktop failed", exc_info=True)
        return None

"""Global low-level mouse/keyboard hooks.

The callback must return as quickly as possible: Windows removes a low-level
hook whose callback blocks for too long.  All callbacks here only mutate a few
fields and enqueue work in the controller.
"""

from __future__ import annotations

import ctypes
import logging
import os
import threading
import time
from ctypes import wintypes

from ..constants import (
    DOUBLE_TAP_INTERVAL,
    LLKHF_INJECTED,
    LLMHF_INJECTED,
    MOD_ALT,
    MOD_CONTROL,
    MOD_SHIFT,
    MOD_WIN,
    MULTI_DOUBLE_PRESS,
    TAP_MAX_DURATION,
    TRIGGER_ALT_LEFT,
    TRIGGER_MIDDLE,
    VK_CONTROL,
    VK_LWIN,
    VK_MENU,
    VK_RWIN,
    VK_SHIFT,
    WH_KEYBOARD_LL,
    WH_MOUSE_LL,
    WM_KEYDOWN,
    WM_KEYUP,
    WM_LBUTTONDOWN,
    WM_LBUTTONUP,
    WM_MBUTTONDOWN,
    WM_MBUTTONUP,
    WM_MOUSEMOVE,
    WM_SYSKEYDOWN,
    WM_SYSKEYUP,
)
from . import win32

log = logging.getLogger(__name__)

VK_LMENU = 0xA4
VK_RMENU = 0xA5
VK_TAB = 0x09

MODIFIER_VKS = {
    VK_CONTROL,
    VK_SHIFT,
    VK_MENU,
    VK_LWIN,
    VK_RWIN,
    VK_LMENU,
    VK_RMENU,
    0xA0,  # VK_LSHIFT
    0xA1,  # VK_RSHIFT
    0xA2,  # VK_LCONTROL
    0xA3,  # VK_RCONTROL
}


class HookThread(threading.Thread):
    def __init__(self) -> None:
        super().__init__(name="Win32InputHook", daemon=True)
        self.enabled = True
        self.draw_trigger = TRIGGER_ALT_LEFT
        self.multi_stroke_mode = MULTI_DOUBLE_PRESS
        self.capturing_keys = False
        self._capture_modifiers = 0

        self.alt_down = False
        self.multi_session = False
        self._drawing = False
        self._draw_button: str | None = None
        self._keys_down: set[int] = set()

        self._thread_id = 0
        self._mouse_hook = None
        self._keyboard_hook = None
        self._ready = threading.Event()
        self._stopping = False
        self.error: str | None = None
        self.ignore_injected = os.environ.get("MAGICALLY_ENCIRCLE_TEST_INPUT") != "1"
        log.info("Hook ignore_injected=%s", self.ignore_injected)

        # Callbacks assigned by the controller.  All are called on the hook
        # thread; the controller should only enqueue events.
        self.on_begin = None  # (x, y, t)
        self.on_move = None  # (x, y, t)
        self.on_end = None  # (x, y, t)
        self.on_alt_released = None  # ()
        self.on_key_captured = None  # (vk, modifiers)

    # ------------------------------------------------------------------
    def start_hooks(self, timeout: float = 2.0) -> bool:
        self.start()
        self._ready.wait(timeout)
        return self.error is None and self.is_alive()

    def stop_hooks(self) -> None:
        self._stopping = True
        if self._thread_id:
            try:
                win32.user32.PostThreadMessageW(self._thread_id, win32.WM_QUIT, 0, 0)
            except Exception:
                pass
        self.join(timeout=2.0)

    def run(self) -> None:
        self._thread_id = win32.kernel32.GetCurrentThreadId()
        module = win32.kernel32.GetModuleHandleW(None)
        self._mouse_proc = win32.MOUSEHOOKPROC(self._mouse_callback)
        self._keyboard_proc = win32.KEYHOOKPROC(self._keyboard_callback)
        try:
            self._mouse_hook = win32.user32.SetWindowsHookExW(
                WH_MOUSE_LL, self._mouse_proc, module, 0
            )
            self._keyboard_hook = win32.user32.SetWindowsHookExW(
                WH_KEYBOARD_LL, self._keyboard_proc, module, 0
            )
        except Exception as exc:  # pragma: no cover - depends on Win32
            self.error = str(exc)
            log.exception("Could not install global hooks")
            self._ready.set()
            return
        if not self._mouse_hook or not self._keyboard_hook:
            self.error = f"SetWindowsHookEx failed (error {ctypes.get_last_error()})"
            log.error(self.error)
            self._ready.set()
            return
        self._ready.set()
        log.info("Global hooks installed")

        msg = win32.MSG()
        try:
            while not self._stopping:
                result = win32.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result == 0 or result == -1:
                    break
                win32.user32.TranslateMessage(ctypes.byref(msg))
                win32.user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            self._unhook()

    def _unhook(self) -> None:
        try:
            if self._mouse_hook:
                win32.user32.UnhookWindowsHookEx(self._mouse_hook)
            if self._keyboard_hook:
                win32.user32.UnhookWindowsHookEx(self._keyboard_hook)
        except Exception:
            pass
        self._mouse_hook = None
        self._keyboard_hook = None
        log.info("Global hooks removed")

    def _next(self, n_code: int, w_param: int, l_param: int):
        return win32.user32.CallNextHookEx(None, n_code, w_param, l_param)

    # ------------------------------------------------------------------
    def _mouse_callback(self, n_code: int, w_param: int, l_param: int):
        if n_code < 0:
            return self._next(n_code, w_param, l_param)
        try:
            info = ctypes.cast(l_param, ctypes.POINTER(win32.MSLLHOOKSTRUCT)).contents
            if self.ignore_injected and (info.flags & LLMHF_INJECTED):
                return self._next(n_code, w_param, l_param)

            message = int(w_param)
            x, y = info.pt.x, info.pt.y
            now = time.perf_counter()

            if not self.enabled:
                if self._drawing:
                    self._drawing = False
                    if self.on_end:
                        self.on_end(x, y, now)
                return self._next(n_code, w_param, l_param)

            if message == WM_MOUSEMOVE and self._drawing:
                if self.on_move:
                    self.on_move(x, y, now)
                # Do NOT swallow mouse moves: Windows uses the move event to
                # update the real cursor position.  Swallowing it would freeze
                # the cursor while the user is drawing.  The button down/up
                # events are still swallowed, so the target app never sees a
                # click or drag.
                return self._next(n_code, w_param, l_param)

            if message == WM_LBUTTONDOWN and self.draw_trigger == TRIGGER_ALT_LEFT:
                if win32.is_key_down(VK_MENU):
                    self._drawing = True
                    self._draw_button = "left"
                    if self.on_begin:
                        self.on_begin(x, y, now)
                    return 1
                return self._next(n_code, w_param, l_param)

            if message == WM_MBUTTONDOWN and self.draw_trigger == TRIGGER_MIDDLE:
                self._drawing = True
                self._draw_button = "middle"
                if self.on_begin:
                    self.on_begin(x, y, now)
                return 1

            if message == WM_LBUTTONUP and self._drawing and self._draw_button == "left":
                self._drawing = False
                self._draw_button = None
                if self.on_end:
                    self.on_end(x, y, now)
                return 1

            if message == WM_MBUTTONUP and self._drawing and self._draw_button == "middle":
                self._drawing = False
                self._draw_button = None
                if self.on_end:
                    self.on_end(x, y, now)
                return 1

            return self._next(n_code, w_param, l_param)
        except Exception:
            log.exception("Mouse hook callback failed")
            return self._next(n_code, w_param, l_param)

    # ------------------------------------------------------------------
    def _keyboard_callback(self, n_code: int, w_param: int, l_param: int):
        if n_code < 0:
            return self._next(n_code, w_param, l_param)
        try:
            info = ctypes.cast(l_param, ctypes.POINTER(win32.KBDLLHOOKSTRUCT)).contents
            if self.ignore_injected and (info.flags & LLKHF_INJECTED):
                return self._next(n_code, w_param, l_param)

            message = int(w_param)
            vk = int(info.vkCode)
            now = time.perf_counter()

            if self.capturing_keys:
                if message in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    if vk not in self._keys_down:
                        self._keys_down.add(vk)
                        modifier_bit = self._modifier_bit(vk)
                        if modifier_bit:
                            self._capture_modifiers |= modifier_bit
                        elif self.on_key_captured:
                            modifiers = win32.modifiers_from_state() | self._capture_modifiers
                            self.on_key_captured(vk, modifiers)
                elif message in (WM_KEYUP, WM_SYSKEYUP):
                    self._keys_down.discard(vk)
                    modifier_bit = self._modifier_bit(vk)
                    if modifier_bit:
                        self._capture_modifiers &= ~modifier_bit
                return 1

            if vk in (VK_MENU, VK_LMENU, VK_RMENU):
                if message in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    if not self.alt_down:
                        self.alt_down = True
                        self.alt_down_time = now
                        if self.multi_stroke_mode == MULTI_DOUBLE_PRESS:
                            is_double = (
                                getattr(self, "last_alt_was_tap", False)
                                and (now - getattr(self, "last_alt_up_time", 0.0))
                                < DOUBLE_TAP_INTERVAL
                            )
                            self.multi_session = is_double
                        else:
                            self.multi_session = True
                elif message in (WM_KEYUP, WM_SYSKEYUP):
                    if self.alt_down:
                        self.alt_down = False
                        self.last_alt_was_tap = (now - self.alt_down_time) < TAP_MAX_DURATION
                        self.last_alt_up_time = now
                        if self.multi_session:
                            self.multi_session = False
                            if self.on_alt_released:
                                self.on_alt_released()
                return self._next(n_code, w_param, l_param)

            return self._next(n_code, w_param, l_param)
        except Exception:
            log.exception("Keyboard hook callback failed")
            return self._next(n_code, w_param, l_param)

    # ------------------------------------------------------------------
    @staticmethod
    def _modifier_bit(vk: int) -> int:
        if vk in (VK_CONTROL, 0xA2, 0xA3):
            return MOD_CONTROL
        if vk in (VK_MENU, VK_LMENU, VK_RMENU):
            return MOD_ALT
        if vk in (VK_SHIFT, 0xA0, 0xA1):
            return MOD_SHIFT
        if vk in (VK_LWIN, VK_RWIN):
            return MOD_WIN
        return 0

    def set_capturing(self, value: bool) -> None:
        self.capturing_keys = value
        if value:
            self._keys_down.clear()
            self._capture_modifiers = 0

    def reset_drawing(self) -> None:
        self._drawing = False
        self._draw_button = None
        self.multi_session = False

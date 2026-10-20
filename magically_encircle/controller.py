"""The application coordinator.

This is the Windows counterpart of `MagicController.swift`: it owns the input
state machine, recognition, action dispatch, persistence and the UI-facing
signals.
"""

from __future__ import annotations

import json
import logging
import math
import queue
import threading
import time
import uuid
from pathlib import Path

from PySide6.QtCore import QObject, QRectF, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from .config import (
    Settings,
    atomic_write_json,
)
from . import __version__
from .constants import (
    CLOSE_QUIT_APP,
    CLOSE_TAB,
    CLOSE_WINDOW,
    CUSTOM_THRESHOLD,
    HOLD_DURATION,
    MIN_GESTURE_LENGTH,
    MOD_ALT,
    MOD_CONTROL,
    SYMBOL_THRESHOLD,
    TRIGGER_ALT_LEFT,
    TRIGGER_MIDDLE,
    VK_ESCAPE,
    VK_F4,
    VK_W,
)
from .gesture import geometry
from .gesture.builtin import (
    BUILT_INS,
    BUILT_IN_BY_ACTION,
    BUILT_IN_BY_ID,
    action_shortcut,
    find_builtin,
    swipe_symbol,
)
from .gesture.recognizer import GestureCandidate, recognizer
from .model.gestures import (
    COORDS_APPKIT,
    COORDS_SCREEN,
    BuiltInShortcut,
    BuiltInShortcutStore,
    CustomGesture,
    CustomGestureStore,
    GestureOverrideStore,
    Strokes,
    strokes_from_json,
    strokes_to_json,
)
from .playback import PatternPlayer
from .platform_support import autostart, capture, ocr, sender, virtual_desktop, win32
from .platform_support.hooks import HookThread
from .platform_support.overlay import OverlayManager, OverlayWindow, STYLE_TITLES, STYLES
from .ui.hud import HudWindow
from .ui.theme import preview_pixmap
from .platform_support.updates import UpdateChecker

log = logging.getLogger(__name__)

MIDDLE_SPEEDS = {"fast": 0.2, "normal": 0.5, "slow": 0.75}


class MagicController(QObject):
    stateChanged = Signal()
    ocrFinished = Signal(bool, str, str)  # success, text, message

    def __init__(self, app: QApplication, settings: Settings) -> None:
        super().__init__()
        self.app = app
        self.settings = settings
        self.store = CustomGestureStore()
        self.override_store = GestureOverrideStore()
        self.builtin_store = BuiltInShortcutStore()

        self.custom_gestures: list[CustomGesture] = self.store.load()
        self.gesture_overrides: dict[str, list[Strokes]] = self.override_store.load()
        self.builtin_shortcuts: dict[str, BuiltInShortcut] = self.builtin_store.load()

        self.overlay_manager = OverlayManager()
        self.overlay_manager.set_style(settings.style)
        self.hud = HudWindow()
        self.player = PatternPlayer()

        self._events: queue.Queue = queue.Queue()
        self._hook = HookThread()
        self._hook.enabled = settings.enabled
        self._hook.draw_trigger = settings.draw_trigger
        self._hook.multi_stroke_mode = settings.multi_stroke_mode
        self._hook.on_begin = lambda x, y, t: self._events.put(("begin", x, y, t))
        self._hook.on_move = lambda x, y, t: self._events.put(("move", x, y, t))
        self._hook.on_end = lambda x, y, t: self._events.put(("end", x, y, t))
        self._hook.on_alt_released = lambda: self._events.put(("alt_released",))
        self._hook.on_key_captured = lambda vk, mods: self._events.put(("key", vk, mods))

        self._current_overlay: OverlayWindow | None = None
        self._current_points: list[tuple[float, float]] = []
        self._multi_strokes: list[list[tuple[float, float]]] = []
        self._stroke_closed = False
        self._did_capture = False
        self._capture_busy = False
        self._is_multi_stroke = False
        self._recording_mode: tuple[str, str | None] | None = None
        self._pending_key_target: tuple[str, str] | None = None
        self._preview_cache: dict[str, QPixmap] = {}

        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self.perform_lasso_capture)
        self._middle_timer = QTimer(self)
        self._middle_timer.setSingleShot(True)
        self._middle_timer.timeout.connect(self._finalize_middle_strokes)

        self._drain_timer = QTimer(self)
        self._drain_timer.setInterval(8)
        self._drain_timer.timeout.connect(self._drain_events)
        self._watchdog = QTimer(self)
        self._watchdog.setInterval(5000)
        self._watchdog.timeout.connect(self._check_hooks)
        self._desktop_timer = QTimer(self)
        self._desktop_timer.setInterval(2000)
        self._desktop_timer.timeout.connect(self._check_desktop)

        self._update_checker = UpdateChecker()
        self._update_checker.result_ready.connect(self._on_update_result)
        self.ocrFinished.connect(self._on_ocr_finished)
        self.overlay_manager.can_rebuild = (
            lambda: self._current_overlay is None
            and not self.player.is_playing
            and not self._capture_busy
        )

        self._started = False
        self._hook_alerted = False
        self.start()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._drain_timer.start()
        self._watchdog.start()
        self._desktop_timer.start()
        if not self._hook.start_hooks():
            message = self._hook.error or "无法安装全局输入钩子"
            log.error(message)
            self._hook_alerted = True
            self.show_hud("启动失败", message)
        else:
            self.show_hud(
                "magicallyEncircle 已启动",
                f"按住{self.draw_hint}拖动开始绘制\n托盘图标可打开设置（看不到请点任务栏 ^ 展开）",
            )
        if self.settings.auto_check_updates:
            self._update_checker.check(False)

    def shutdown(self) -> None:
        log.info("Shutting down")
        self._drain_timer.stop()
        self._watchdog.stop()
        self._desktop_timer.stop()
        self._hold_timer.stop()
        self._middle_timer.stop()
        self.player.cancel()
        try:
            self._hook.stop_hooks()
        except Exception:
            pass
        for overlay in self.overlay_manager.all_overlays():
            overlay.close()
        self.hud.close()
        self.settings.save()
        self.store.save(self.custom_gestures)
        self.override_store.save(self.gesture_overrides)
        self.builtin_store.save(self.builtin_shortcuts)

    def _check_hooks(self) -> None:
        if not self._hook.is_alive():
            log.warning("Input hook thread died, restarting")
            self._hook = HookThread()
            self._hook.enabled = self.settings.enabled
            self._hook.draw_trigger = self.settings.draw_trigger
            self._hook.multi_stroke_mode = self.settings.multi_stroke_mode
            self._hook.on_begin = lambda x, y, t: self._events.put(("begin", x, y, t))
            self._hook.on_move = lambda x, y, t: self._events.put(("move", x, y, t))
            self._hook.on_end = lambda x, y, t: self._events.put(("end", x, y, t))
            self._hook.on_alt_released = lambda: self._events.put(("alt_released",))
            self._hook.on_key_captured = lambda vk, mods: self._events.put(("key", vk, mods))
            if not self._hook.start_hooks():
                if not self._hook_alerted:
                    self.show_hud("输入钩子已断开", "请尝试退出后重新启动应用")
                    self._hook_alerted = True
            else:
                self._hook_alerted = False

    # ------------------------------------------------------------------
    # Virtual desktops
    # ------------------------------------------------------------------
    def _overlay_desktop_state(self) -> bool | None:
        overlays = self.overlay_manager.all_overlays()
        if not overlays:
            return None
        try:
            log.debug("Checking overlay desktop state for hwnd %s", int(overlays[0].winId()))
            state = virtual_desktop.is_window_on_current_desktop(int(overlays[0].winId()))
            log.debug("Overlay desktop state: %s", state)
            return state
        except Exception:
            log.debug("Overlay desktop state check failed", exc_info=True)
            return None

    def _ensure_overlays_on_current_desktop(self) -> None:
        if self._overlay_desktop_state() is False:
            log.info("Overlay is on another virtual desktop; recreating")
            self.overlay_manager.rebuild()
            self.overlay_manager.set_style(self.settings.style)

    def _check_desktop(self) -> None:
        if self._current_overlay is not None or self._capture_busy or self.player.is_playing:
            return
        self._ensure_overlays_on_current_desktop()

    # ------------------------------------------------------------------
    # Settings / simple state
    # ------------------------------------------------------------------
    @property
    def draw_hint(self) -> str:
        return "鼠标中键" if self.settings.draw_trigger == TRIGGER_MIDDLE else "Alt + 左键"

    @property
    def is_enabled(self) -> bool:
        return self.settings.enabled

    def set_enabled(self, enabled: bool) -> None:
        self.settings.enabled = enabled
        self._hook.enabled = enabled
        if not enabled:
            self._hook.reset_drawing()
            self.cancel_key_capture(silent=True)
            self._hold_timer.stop()
            self._middle_timer.stop()
            self.player.cancel()
            self._reset_stroke_state()
            self._multi_strokes.clear()
            self._current_overlay = None
            self._is_multi_stroke = False
            for overlay in self.overlay_manager.all_overlays():
                overlay.pins_strokes = False
                overlay.release_pinned_strokes(time.perf_counter())
        self.show_hud("已启用魔法线条" if enabled else "已停用魔法线条", "")
        self.stateChanged.emit()

    def toggle_enabled(self) -> None:
        self.set_enabled(not self.settings.enabled)

    def set_show_hud(self, value: bool) -> None:
        self.settings.show_hud = value
        if not value:
            self.hud.hide_now()
        self.stateChanged.emit()

    def toggle_hud(self) -> None:
        self.set_show_hud(not self.settings.show_hud)

    def set_style(self, style: str) -> None:
        if style not in STYLES and style != "random":
            style = "whiteOrange"
        self.settings.style = style
        self.overlay_manager.set_style(style)
        self.show_hud("视觉风格", STYLE_TITLES.get(style, style))
        self.stateChanged.emit()

    def set_draw_trigger(self, trigger: str) -> None:
        if trigger not in (TRIGGER_ALT_LEFT, TRIGGER_MIDDLE):
            return
        self.settings.draw_trigger = trigger
        self._hook.draw_trigger = trigger
        self.cancel_key_capture(silent=True)
        self.stateChanged.emit()

    def set_multi_stroke_mode(self, mode: str) -> None:
        self.settings.multi_stroke_mode = mode
        self._hook.multi_stroke_mode = mode
        self.stateChanged.emit()

    def set_middle_speed(self, speed: str) -> None:
        if speed not in MIDDLE_SPEEDS:
            speed = "normal"
        self.settings.middle_speed = speed
        self.stateChanged.emit()

    def set_close_action(self, action: str) -> None:
        if action not in (CLOSE_WINDOW, CLOSE_TAB, CLOSE_QUIT_APP):
            action = CLOSE_WINDOW
        self.settings.close_action = action
        self.stateChanged.emit()

    def set_playback_speed(self, speed: float) -> None:
        self.settings.playback_speed = speed
        self.stateChanged.emit()

    def set_auto_check_updates(self, enabled: bool) -> None:
        self.settings.auto_check_updates = enabled
        self.stateChanged.emit()

    def set_launch_at_login(self, enabled: bool) -> None:
        if autostart.set_enabled(enabled):
            self.settings.launch_at_login = enabled
        else:
            self.settings.launch_at_login = autostart.is_enabled()
            self.show_hud("设置开机自启动失败", "请把应用放在有写入权限的位置后重试")
        self.stateChanged.emit()

    def show_hud(self, title: str, detail: str = "", near: tuple[float, float] | None = None) -> None:
        if not self.settings.show_hud:
            return
        if near is None:
            near = self._current_points[-1] if self._current_points else None
        try:
            self.hud.show_message(title, detail, near)
        except Exception:
            log.exception("Could not show HUD")

    # ------------------------------------------------------------------
    # Event pump
    # ------------------------------------------------------------------
    def _drain_events(self) -> None:
        if self._capture_busy:
            return
        processed = 0
        while processed < 3000:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                break
            processed += 1
            try:
                kind = event[0]
                if kind == "begin":
                    self._on_begin(event[1], event[2], event[3])
                elif kind == "move":
                    self._on_move(event[1], event[2], event[3])
                elif kind == "end":
                    self._on_end(event[1], event[2], event[3])
                elif kind == "alt_released":
                    self._on_alt_released()
                elif kind == "key":
                    self._handle_captured_key(event[1], event[2])
            except Exception:
                log.exception("Input event failed: %s", event)

    # ------------------------------------------------------------------
    # Drawing state machine
    # ------------------------------------------------------------------
    def _reset_stroke_state(self) -> None:
        self._current_points = []
        self._stroke_closed = False
        self._did_capture = False
        self._hold_timer.stop()

    def _on_begin(self, x: int, y: int, t: float) -> None:
        if not self.settings.enabled:
            return
        self._ensure_overlays_on_current_desktop()
        info = self.overlay_manager.point_from_physical(x, y)
        if info is None or info[1] is None:
            return
        _monitor, overlay, local, global_point = info
        self.player.cancel()

        self._reset_stroke_state()
        self._is_multi_stroke = (
            self.settings.draw_trigger == TRIGGER_MIDDLE
            or (self.settings.draw_trigger == TRIGGER_ALT_LEFT and self._hook.multi_session)
        )
        if not self._is_multi_stroke:
            self._multi_strokes.clear()
            self._release_pinned_all()

        self._current_overlay = overlay
        overlay.pins_strokes = self._is_multi_stroke
        overlay.ensure_visible()
        self._current_points = [global_point]
        overlay.begin_stroke(local, t)

        if self.settings.draw_trigger == TRIGGER_MIDDLE:
            self._middle_timer.stop()

    def _on_move(self, x: int, y: int, t: float) -> None:
        if not self.settings.enabled or self._did_capture or self._current_overlay is None:
            return
        info = self.overlay_manager.point_from_physical(x, y)
        if info is None or info[1] is None:
            return
        _monitor, overlay, local, global_point = info
        if overlay is not self._current_overlay:
            self._current_overlay.finish_stroke(t)
            overlay.pins_strokes = self._is_multi_stroke
            overlay.ensure_visible()
            self._current_overlay = overlay
            overlay.begin_stroke(local, t)
        else:
            overlay.extend_stroke(local, t)
        self._current_points.append(global_point)

        if (
            not self._recording_mode
            and not self._stroke_closed
            and len(self._current_points) >= 8
            and len(self._current_points) % 3 == 0
            and geometry.is_closed_loop(self._current_points)
        ):
            self._stroke_closed = True
            self._hold_timer.start(int(HOLD_DURATION * 1000))

    def _on_end(self, x: int, y: int, t: float) -> None:
        log.debug("End point: (%s, %s), current points=%s", x, y, len(self._current_points))
        if self._current_overlay is None:
            self._reset_stroke_state()
            return
        info = self.overlay_manager.point_from_physical(x, y)
        if info is not None and info[1] is not None:
            _monitor, overlay, local, global_point = info
            if overlay is not self._current_overlay:
                self._current_overlay.finish_stroke(t)
                overlay.pins_strokes = self._is_multi_stroke
                overlay.ensure_visible()
                self._current_overlay = overlay
                overlay.begin_stroke(local, t)
            else:
                overlay.extend_stroke(local, t)
            if not self._current_points or global_point != self._current_points[-1]:
                self._current_points.append(global_point)

        self._hold_timer.stop()
        self._current_overlay.finish_stroke(t)
        captured = self._did_capture
        multi = self._is_multi_stroke
        middle = self.settings.draw_trigger == TRIGGER_MIDDLE

        if captured:
            self._release_pinned_all()
        elif multi and not middle:
            if self._stroke_closed:
                self.perform_lasso_copy()
            elif len(self._current_points) >= 2:
                self._multi_strokes.append(list(self._current_points))
        elif middle:
            if self._stroke_closed:
                self.perform_lasso_copy()
            elif len(self._current_points) >= 2:
                self._multi_strokes.append(list(self._current_points))
            self._restart_middle_timer()
        elif self._recording_mode:
            self._handle_recorded([list(self._current_points)])
        else:
            self.handle_recognized_strokes([list(self._current_points)], closed=self._stroke_closed)

        self._current_overlay = None
        self._reset_stroke_state()

    def _on_alt_released(self) -> None:
        strokes = self._multi_strokes
        self._multi_strokes = []
        self._is_multi_stroke = False
        self._release_pinned_all()
        if not strokes:
            return
        if self._recording_mode:
            self._handle_recorded(strokes)
        else:
            self.handle_recognized_strokes(strokes, closed=False)

    def _restart_middle_timer(self) -> None:
        delay = MIDDLE_SPEEDS.get(self.settings.middle_speed, 0.5)
        self._middle_timer.start(int(delay * 1000))

    def _finalize_middle_strokes(self) -> None:
        self._middle_timer.stop()
        strokes = self._multi_strokes
        self._multi_strokes = []
        self._release_pinned_all()
        if not strokes:
            return
        if self._recording_mode:
            self._handle_recorded(strokes)
        else:
            self.handle_recognized_strokes(strokes, closed=False)

    def _release_pinned_all(self) -> None:
        now = time.perf_counter()
        for overlay in self.overlay_manager.all_overlays():
            overlay.pins_strokes = False
            overlay.release_pinned_strokes(now)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------
    def begin_recording_gesture(self) -> None:
        self.cancel_key_capture(silent=True)
        self._multi_strokes.clear()
        self._release_pinned_all()
        self._recording_mode = ("custom", None)
        self.show_hud("记录图案中", f"用{self.draw_hint}画一个图案")
        self.stateChanged.emit()

    def begin_recording_builtin_override(self, identifier: str) -> None:
        built_in = find_builtin(identifier)
        if built_in is None:
            return
        self.cancel_key_capture(silent=True)
        self._multi_strokes.clear()
        self._release_pinned_all()
        self._recording_mode = ("builtin", identifier)
        self.show_hud(f"录制「{built_in.title}」的图案", f"用{self.draw_hint}画一个图案")
        self.stateChanged.emit()

    def cancel_recording(self) -> None:
        if self._recording_mode is None:
            return
        self._recording_mode = None
        self.show_hud("已取消记录", "")
        self.stateChanged.emit()

    @property
    def is_recording(self) -> bool:
        return self._recording_mode is not None

    @property
    def recording_builtin_id(self) -> str | None:
        if self._recording_mode and self._recording_mode[0] == "builtin":
            return self._recording_mode[1]
        return None

    def _handle_recorded(self, strokes: Strokes) -> None:
        mode = self._recording_mode
        self._recording_mode = None
        if mode is None:
            return
        if mode[0] == "custom":
            self._save_recorded_custom(strokes)
        elif mode[1]:
            self._save_builtin_override(mode[1], strokes)

    def _save_recorded_custom(self, strokes: Strokes) -> None:
        valid = [stroke for stroke in strokes if len(stroke) >= 2]
        total = sum(geometry.path_length(stroke) for stroke in valid)
        if not valid or total <= MIN_GESTURE_LENGTH:
            self.show_hud("图案太短", "请重新记录")
            self.stateChanged.emit()
            return
        gesture = CustomGesture.new(self.unique_name(f"图案{len(self.custom_gestures) + 1}"), valid)
        self.custom_gestures.append(gesture)
        self.store.save(self.custom_gestures)
        kind = f"（{len(valid)} 笔）" if len(valid) > 1 else ""
        self.show_hud(f"已保存 {gesture.name}{kind}", "到「设置 → 自定义图案」绑定快捷键")
        self.stateChanged.emit()

    def _save_builtin_override(self, identifier: str, strokes: Strokes) -> None:
        valid = [stroke for stroke in strokes if len(stroke) >= 2]
        total = sum(geometry.path_length(stroke) for stroke in valid)
        if not valid or total <= MIN_GESTURE_LENGTH:
            self.show_hud("图案太短", "请重新录制")
            self.stateChanged.emit()
            return
        samples = self.gesture_overrides.setdefault(identifier, [])
        samples.append(valid)
        self.override_store.save(self.gesture_overrides)
        title = find_builtin(identifier).title if find_builtin(identifier) else identifier
        self.show_hud(f"已更新「{title}」", f"现在有 {len(samples)} 份自定义图案")
        self.stateChanged.emit()

    def set_builtin_override(self, identifier: str, strokes: Strokes) -> None:
        """Save a sample recorded in the Settings canvas."""
        self._save_builtin_override(identifier, strokes)

    def reset_builtin(self, identifier: str) -> None:
        built_in = find_builtin(identifier)
        self.gesture_overrides.pop(identifier, None)
        self.builtin_shortcuts.pop(identifier, None)
        self.override_store.save(self.gesture_overrides)
        self.builtin_store.save(self.builtin_shortcuts)
        self.show_hud("已恢复默认", built_in.title if built_in else identifier)
        self.stateChanged.emit()

    def reset_all_builtin_overrides(self) -> None:
        if not self.gesture_overrides:
            return
        self.gesture_overrides.clear()
        self.override_store.save(self.gesture_overrides)
        self.show_hud("已全部恢复默认图案", "")
        self.stateChanged.emit()

    def has_override(self, identifier: str) -> bool:
        return bool(self.gesture_overrides.get(identifier))

    def override_count(self, identifier: str) -> int:
        return len(self.gesture_overrides.get(identifier, []))

    def has_builtin_shortcut_override(self, identifier: str) -> bool:
        return identifier in self.builtin_shortcuts

    # ------------------------------------------------------------------
    # Custom gesture management
    # ------------------------------------------------------------------
    def add_custom_gesture(self, name: str, strokes: Strokes) -> None:
        valid = [stroke for stroke in strokes if len(stroke) >= 2]
        if not valid:
            return
        stripped = name.strip()
        resolved = stripped if stripped else f"图案{len(self.custom_gestures) + 1}"
        resolved = self.unique_name(resolved)
        self.custom_gestures.append(CustomGesture.new(resolved, valid))
        self._persist_gestures()
        self.show_hud("已保存图案", resolved)
        self.stateChanged.emit()

    def rename_gesture(self, identifier: str, new_name: str) -> None:
        name = new_name.strip()
        if not name:
            return
        for gesture in self.custom_gestures:
            if gesture.id == identifier:
                gesture.name = name
                self._persist_gestures()
                self.stateChanged.emit()
                return

    def delete_gesture(self, identifier: str) -> None:
        self.custom_gestures = [g for g in self.custom_gestures if g.id != identifier]
        self._preview_cache.pop(identifier, None)
        if self._pending_key_target == ("custom", identifier):
            self.cancel_key_capture(silent=True)
        self._persist_gestures()
        self.stateChanged.emit()

    def _persist_gestures(self) -> None:
        self.store.save(self.custom_gestures)

    def unique_name(self, base: str) -> str:
        existing = {gesture.name for gesture in self.custom_gestures}
        if base not in existing:
            return base
        index = 2
        while f"{base} {index}" in existing:
            index += 1
        return f"{base} {index}"

    def set_custom_shortcut(self, identifier: str, vk: int, modifiers: int, display: str) -> None:
        for gesture in self.custom_gestures:
            if gesture.id == identifier:
                gesture.key_code = int(vk)
                gesture.modifier_flags = int(modifiers)
                gesture.key_display = display
                gesture.app_paths = None
                gesture.imported_display = ""
                self._persist_gestures()
                self.show_hud("已绑定", f"{gesture.name} → {display}")
                self.stateChanged.emit()
                return

    def set_custom_apps(self, identifier: str, paths: list[str]) -> None:
        for gesture in self.custom_gestures:
            if gesture.id == identifier:
                gesture.app_paths = list(paths) if paths else None
                gesture.key_code = None
                gesture.modifier_flags = 0
                gesture.key_display = ""
                gesture.imported_display = ""
                self._persist_gestures()
                if paths:
                    names = "、".join(self.app_display_name(path) for path in paths)
                    self.show_hud(gesture.name, f"已绑定 {names}")
                self.stateChanged.emit()
                return

    def clear_custom_binding(self, identifier: str) -> None:
        for gesture in self.custom_gestures:
            if gesture.id == identifier:
                gesture.key_code = None
                gesture.modifier_flags = 0
                gesture.key_display = ""
                gesture.app_paths = None
                gesture.imported_display = ""
                self._persist_gestures()
                self.show_hud(gesture.name, "已清除绑定")
                self.stateChanged.emit()
                return

    def binding_summary(self, gesture: CustomGesture) -> str:
        if gesture.is_shortcut_bound:
            return gesture.key_display
        if gesture.is_app_bound:
            return "打开 " + "、".join(self.app_display_name(path) for path in (gesture.app_paths or []))
        if gesture.imported_display:
            return f"未绑定（原 {gesture.imported_display}）"
        return "未绑定"

    @staticmethod
    def app_display_name(path: str) -> str:
        name = Path(path).name
        lower = name.lower()
        if lower.endswith(".exe") or lower.endswith(".lnk"):
            return name[:-4]
        return name

    def preview_image(self, gesture: CustomGesture) -> QPixmap:
        cached = self._preview_cache.get(gesture.id)
        if cached is not None:
            return cached
        pixmap = preview_pixmap(gesture.strokes, 64)
        self._preview_cache[gesture.id] = pixmap
        return pixmap

    # ------------------------------------------------------------------
    # Key capture
    # ------------------------------------------------------------------
    @property
    def pending_key_target(self) -> tuple[str, str] | None:
        return self._pending_key_target

    @property
    def pending_key_display(self) -> str | None:
        return None

    def begin_key_capture(self, target: tuple[str, str]) -> None:
        kind, identifier = target
        if kind == "builtin":
            built_in = find_builtin(identifier)
            if built_in is None or built_in.action == "close":
                return
            title = built_in.title
        else:
            gesture = next((g for g in self.custom_gestures if g.id == identifier), None)
            if gesture is None:
                return
            title = gesture.name
        self._recording_mode = None
        self._multi_strokes.clear()
        self._release_pinned_all()
        self._pending_key_target = target
        self._hook.set_capturing(True)
        self.show_hud(f"为「{title}」设置快捷键", "请按下快捷键（Esc 取消）")
        self.stateChanged.emit()

    def cancel_key_capture(self, silent: bool = False) -> None:
        if self._pending_key_target is None:
            return
        self._pending_key_target = None
        self._hook.set_capturing(False)
        if not silent:
            self.show_hud("已取消绑定", "")
        self.stateChanged.emit()

    def _handle_captured_key(self, vk: int, modifiers: int) -> None:
        target = self._pending_key_target
        if target is None:
            return
        if vk == VK_ESCAPE:
            self.cancel_key_capture()
            return
        display = win32.shortcut_display(vk, modifiers)
        kind, identifier = target
        if kind == "builtin":
            built_in = find_builtin(identifier)
            if built_in is None:
                self.cancel_key_capture(silent=True)
                return
            self.builtin_shortcuts[identifier] = BuiltInShortcut(vk, modifiers, display)
            self.builtin_store.save(self.builtin_shortcuts)
            self.show_hud("已绑定", f"{built_in.title} → {display}")
        else:
            self.set_custom_shortcut(identifier, vk, modifiers, display)
        self._pending_key_target = None
        self._hook.set_capturing(False)
        self.stateChanged.emit()

    # ------------------------------------------------------------------
    # Recognition and actions
    # ------------------------------------------------------------------
    def _custom_candidates(self) -> list[GestureCandidate]:
        return [
            GestureCandidate(gesture.name, gesture.strokes, None, gesture.id)
            for gesture in self.custom_gestures
            if gesture.is_bound
        ]

    def _builtin_candidates(self) -> list[GestureCandidate]:
        result: list[GestureCandidate] = []
        for built_in in BUILT_INS:
            samples = self.gesture_overrides.get(built_in.id)
            if samples:
                for sample in samples:
                    result.append(GestureCandidate(built_in.title, sample, built_in.action))
            else:
                for sample in built_in.default_samples:
                    result.append(GestureCandidate(built_in.title, sample, built_in.action))
        return result

    def handle_recognized_strokes(self, strokes: Strokes, closed: bool = False) -> None:
        if not strokes:
            return
        log.debug("Recognising strokes: %s", strokes)
        candidates = self._custom_candidates() + self._builtin_candidates()
        ranked = recognizer.ranked(strokes, candidates)
        ranking = self._ranking_text(ranked)

        if len(strokes) == 1:
            direction = geometry.swipe_direction(strokes[0])
            if direction:
                for built_in in BUILT_INS:
                    if built_in.default_swipe == direction and not self.has_override(built_in.id):
                        self.perform_builtin(built_in.action, "滑动\n" + ranking)
                        return

        best = ranked[0] if ranked else None
        if best and best[0].custom_id and best[1] >= CUSTOM_THRESHOLD:
            log.info("Recognised custom gesture %s (%.0f%%)", best[0].name, best[1] * 100)
            self.perform_custom_gesture(best[0].custom_id, best[1], ranking)
            return

        if closed:
            log.info("Recognised closed loop")
            self.perform_lasso_copy()
            return

        if best and best[0].action and best[1] >= SYMBOL_THRESHOLD:
            log.info("Recognised built-in %s (%.0f%%)", best[0].action, best[1] * 100)
            self.perform_builtin(
                best[0].action,
                f"{best[0].name} {best[1] * 100:.0f}%\n{ranking}",
            )
            return

        log.info("Gesture not recognised: %s", ranking.replace("\n", " | "))
        self.show_hud("未识别图案", ranking or "无候选图案")

    @staticmethod
    def _ranking_text(ranked, limit: int = 5) -> str:
        seen: set[str] = set()
        lines: list[str] = []
        for candidate, score in ranked:
            if candidate.name in seen:
                continue
            seen.add(candidate.name)
            lines.append(f"{candidate.name}  {score * 100:.0f}%")
            if len(lines) >= limit:
                break
        return "\n".join(lines)

    def perform_custom_gesture(self, identifier: str, score: float, ranking: str = "") -> None:
        gesture = next((g for g in self.custom_gestures if g.id == identifier), None)
        if gesture is None:
            return
        percent = int(score * 100 + 0.5)
        if gesture.is_app_bound:
            opened, missing = sender.open_paths(gesture.app_paths or [])
            parts = []
            if opened:
                parts.append("打开 " + "、".join(self.app_display_name(path) for path in opened))
            if missing:
                parts.append("、".join(self.app_display_name(path) for path in missing) + " 不存在")
            parts.append(f"匹配 {percent}%")
            self.show_hud(gesture.name, " · ".join(parts))
            return
        if gesture.key_code is None:
            self.show_hud(gesture.name, "未绑定")
            return
        log.info("Custom %s -> %s", gesture.name, gesture.key_display)
        sender.send_shortcut(gesture.key_code, gesture.modifier_flags)
        head = f"{gesture.key_display} · 匹配 {percent}%"
        self.show_hud(gesture.name, head if not ranking else f"{head}\n{ranking}")

    def perform_builtin(self, action: str, extra: str) -> None:
        built_in = BUILT_IN_BY_ACTION.get(action)
        display = ""
        if built_in is not None:
            override = self.builtin_shortcuts.get(built_in.id)
            if override is not None:
                sender.send_shortcut(override.key_code, override.modifier_flags)
                display = override.key_display
            elif action == "close":
                self.perform_close_action()
                display = self.close_action_display()
            elif action == "lockScreen":
                sender.lock_screen()
                display = "锁定屏幕"
            else:
                shortcut = action_shortcut(action)
                if shortcut is not None:
                    if shortcut.special == "lockScreen":
                        sender.lock_screen()
                    elif shortcut.vk:
                        log.info("Built-in %s -> %s", action, shortcut.display)
                        sender.send_shortcut(shortcut.vk, shortcut.modifiers)
                    display = shortcut.display
            title = built_in.title
        else:
            title = action
        detail = display
        if extra:
            detail = f"{detail}   {extra}" if detail else extra
        self.show_hud(title, detail)

    def perform_close_action(self) -> None:
        if self.settings.close_action == CLOSE_TAB:
            sender.send_shortcut(VK_W, MOD_CONTROL)
        else:
            sender.send_shortcut(VK_F4, MOD_ALT)

    def close_action_display(self) -> str:
        if self.settings.close_action == CLOSE_TAB:
            return "Ctrl+W"
        if self.settings.close_action == CLOSE_QUIT_APP:
            return "Alt+F4（退出程序）"
        return "Alt+F4"

    def effective_shortcut_display(self, identifier: str) -> str:
        override = self.builtin_shortcuts.get(identifier)
        if override is not None:
            return override.key_display
        built_in = find_builtin(identifier)
        if built_in is None:
            return ""
        if built_in.action == "close":
            return self.close_action_display()
        shortcut = action_shortcut(built_in.action)
        return shortcut.display if shortcut is not None else ""

    def builtin_description(self, identifier: str) -> str:
        built_in = find_builtin(identifier)
        if built_in is None:
            return ""
        count = self.override_count(identifier)
        if count > 0:
            trigger = f"自定义 {count} 份"
        elif built_in.default_swipe:
            trigger = swipe_symbol(built_in.default_swipe) + " 滑动"
        elif built_in.default_samples:
            trigger = "默认图案"
        else:
            trigger = "未设置"
        shortcut = self.effective_shortcut_display(identifier)
        return f"{shortcut} · {trigger}" if shortcut else trigger

    # ------------------------------------------------------------------
    # Lasso actions
    # ------------------------------------------------------------------
    def _padded_bbox(self) -> QRectF:
        min_x, min_y, width, height = geometry.bounding_box(self._current_points)
        return QRectF(min_x - 6, min_y - 6, width + 12, height + 12)

    def perform_lasso_capture(self) -> None:
        if self._did_capture or self._recording_mode or not self._current_points:
            return
        self._did_capture = True
        self._hold_timer.stop()
        bbox = self._padded_bbox()
        physical = self.overlay_manager.logical_rect_to_physical(bbox)
        if physical is None:
            self.show_hud("截图失败", "无法确定截图区域")
            return
        self.overlay_manager.hide_all()
        self.hud.hide_now()
        self._capture_busy = True
        try:
            QApplication.processEvents()
            time.sleep(0.03)
            image = capture.capture_physical_bbox(physical)
        finally:
            self.overlay_manager.show_all()
            self._capture_busy = False
        if image is None:
            self.show_hud("截图失败", "请稍后重试")
            return
        QApplication.clipboard().setImage(capture.pil_to_qimage(image))
        if self._current_overlay is not None:
            self._current_overlay.finish_stroke(time.perf_counter())
        self.show_hud("已截图圈选区域", "图片已复制到剪贴板")

    def perform_lasso_copy(self) -> None:
        if not self._current_points:
            return
        bbox = self._padded_bbox()
        physical = self.overlay_manager.logical_rect_to_physical(bbox)
        if physical is None:
            self.show_hud("未找到可复制文本", "试着圈住文字再松手")
            return
        self.overlay_manager.hide_all()
        self.hud.hide_now()
        self._capture_busy = True
        try:
            QApplication.processEvents()
            time.sleep(0.03)
            image = capture.capture_physical_bbox(physical)
        finally:
            self.overlay_manager.show_all()
            self._capture_busy = False
        if image is None:
            self.show_hud("未找到可复制文本", "试着圈住文字再松手")
            return

        def worker() -> None:
            text = ocr.recognize(image)
            if text:
                self.ocrFinished.emit(True, text, "")
            else:
                self.ocrFinished.emit(False, "", "")

        threading.Thread(target=worker, name="Ocr", daemon=True).start()

    def _on_ocr_finished(self, success: bool, text: str, message: str) -> None:
        if not success or not text.strip():
            self.show_hud("未找到可复制文本", message or "试着圈住文字再松手")
            return
        QApplication.clipboard().setText(text)
        self.show_hud("已复制圈选文本", f"共 {len(text)} 个字符")

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------
    def play_builtin(self, identifier: str) -> None:
        built_in = find_builtin(identifier)
        if built_in is None:
            return
        samples = self.gesture_overrides.get(identifier)
        if samples:
            self.play_pattern(samples[0])
        elif built_in.default_samples:
            self.play_pattern(built_in.default_samples[0])

    def play_custom_gesture(self, identifier: str) -> None:
        gesture = next((g for g in self.custom_gestures if g.id == identifier), None)
        if gesture is not None:
            self.play_pattern(gesture.strokes)

    def play_pattern(self, strokes: Strokes) -> None:
        valid = [stroke for stroke in strokes if len(stroke) >= 2]
        if not valid:
            return
        x, y = win32.get_cursor_pos()
        info = self.overlay_manager.point_from_physical(x, y)
        if info is None or info[1] is None:
            return
        monitor, overlay, _local, _global = info
        min_x, min_y, width, height = geometry.bounding_box([p for s in valid for p in s])
        max_dimension = max(width, height, 1.0)
        target_size = min(monitor.logical.width(), monitor.logical.height()) * 0.35
        scale = target_size / max_dimension
        center_x = monitor.logical.center().x()
        center_y = monitor.logical.center().y()
        pattern_center_x = min_x + width / 2.0
        pattern_center_y = min_y + height / 2.0
        left = monitor.logical.left()
        top = monitor.logical.top()
        mapped: Strokes = []
        for stroke in valid:
            mapped.append(
                [
                    (
                        center_x + (px - pattern_center_x) * scale - left,
                        center_y + (py - pattern_center_y) * scale - top,
                    )
                    for px, py in stroke
                ]
            )
        overlay.ensure_visible()
        self.player.play(overlay, mapped, self.settings.playback_speed)

    # ------------------------------------------------------------------
    # Import / export
    # ------------------------------------------------------------------
    def build_export_package(self) -> dict:
        overrides = {
            key: [strokes_to_json(sample, y_up=True) for sample in samples]
            for key, samples in self.gesture_overrides.items()
        }
        return {
            "version": 2,
            "platform": "windows",
            "coordinateSystem": COORDS_APPKIT,
            "gestures": [gesture.to_dict(y_up=True) for gesture in self.custom_gestures],
            "builtInOverrides": overrides if overrides else None,
        }

    def export_gestures(self, parent=None) -> None:
        if not self.custom_gestures and not self.gesture_overrides:
            self.show_hud("没有可导出的图案", "")
            return
        path, _filter = QFileDialog.getSaveFileName(
            parent, "导出自定义图案", "magicallyEncircle-gestures.json", "JSON (*.json)"
        )
        if not path:
            return
        package = self.build_export_package()
        try:
            atomic_write_json(Path(path), package)
            override_count = sum(len(samples) for samples in self.gesture_overrides.values())
            self.show_hud("已导出图案", f"{len(self.custom_gestures)} 个自定义 + {override_count} 份内置覆盖")
        except OSError as exc:
            log.exception("Export failed")
            self.show_hud("导出失败", str(exc))

    def import_package(self, data) -> int:
        if isinstance(data, list):
            package = {
                "platform": "macos",
                "coordinateSystem": COORDS_APPKIT,
                "gestures": data,
                "builtInOverrides": None,
            }
        elif isinstance(data, dict):
            package = data
        else:
            raise ValueError("invalid gesture package")

        platform = str(package.get("platform") or "macos")
        coordinate_system = str(package.get("coordinateSystem") or COORDS_APPKIT)
        y_up = coordinate_system != COORDS_SCREEN
        count = 0

        raw_gestures = package.get("gestures")
        if isinstance(raw_gestures, list):
            for item in raw_gestures:
                gesture = CustomGesture.from_dict(item, platform, coordinate_system)
                if gesture is None:
                    continue
                gesture.name = self.unique_name(gesture.name)
                self.custom_gestures.append(gesture)
                count += 1
        self._persist_gestures()

        raw_overrides = package.get("builtInOverrides")
        if isinstance(raw_overrides, dict):
            for identifier, samples in raw_overrides.items():
                if identifier not in BUILT_IN_BY_ID or not isinstance(samples, list):
                    continue
                target = self.gesture_overrides.setdefault(identifier, [])
                for sample in samples:
                    converted = strokes_from_json(sample, y_up=y_up)
                    if converted:
                        target.append(converted)
                        count += 1
            self.override_store.save(self.gesture_overrides)

        self.show_hud("已导入图案", f"{count} 个图案")
        self.stateChanged.emit()
        return count

    def import_gestures(self, parent=None) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            parent, "导入图案", "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as exc:
            log.exception("Import failed")
            self.show_hud("导入失败", "文件格式不正确")
            return

        try:
            self.import_package(data)
        except Exception:
            log.exception("Import failed while merging")
            self.show_hud("导入失败", "文件格式不正确")

    # ------------------------------------------------------------------
    # Updates
    # ------------------------------------------------------------------
    def check_for_updates(self) -> None:
        self._update_checker.check(True)

    def _on_update_result(self, status: str, payload) -> None:
        if status == "update" and isinstance(payload, dict):
            version = payload.get("version", "")
            notes = payload.get("notes") or f"当前版本 {__version__}。"
            box = QMessageBox()
            box.setWindowTitle("发现新版本")
            box.setText(f"发现新版本 {version}")
            box.setInformativeText(str(notes))
            download = box.addButton("前往下载", QMessageBox.AcceptRole)
            box.addButton("稍后", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is download and payload.get("url"):
                QDesktopServices.openUrl(QUrl(str(payload["url"])))
        elif status == "latest":
            QMessageBox.information(None, "检查更新", "已是最新版本。")
        elif status == "error":
            QMessageBox.information(None, "检查更新", "无法获取版本信息，请稍后再试。")

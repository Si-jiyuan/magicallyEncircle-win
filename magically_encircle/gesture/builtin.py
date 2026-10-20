"""Built-in gestures and their Windows action mappings."""

from __future__ import annotations

from dataclasses import dataclass

from ..constants import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_WIN,
    VK_DELETE,
    VK_DOWN,
    VK_LEFT,
    VK_RIGHT,
    VK_UP,
)
from ..model.gestures import Strokes
from .templates_data import TEMPLATES, USER_DRAWN_SAMPLES


def _templates_for(action: str) -> list[Strokes]:
    return [[entry["points"]] for entry in TEMPLATES if entry["action"] == action]


@dataclass(frozen=True)
class BuiltInGesture:
    id: str
    title: str
    action: str
    default_swipe: str | None
    default_samples: list[Strokes]


def _samples(name: str) -> Strokes:
    return USER_DRAWN_SAMPLES[name]


BUILT_INS: list[BuiltInGesture] = [
    BuiltInGesture("back", "后退", "back", "left", []),
    BuiltInGesture("forward", "前进", "forward", "right", []),
    BuiltInGesture("missionControl", "任务视图", "missionControl", "up", []),
    BuiltInGesture("appExpose", "窗口速览", "appExpose", "down", []),
    BuiltInGesture("undo", "撤销", "undo", None, _templates_for("undo")),
    BuiltInGesture("copy", "复制", "copy", None, _templates_for("copy")),
    BuiltInGesture("paste", "粘贴", "paste", None, _templates_for("paste")),
    BuiltInGesture("newTab", "新建标签页", "newTab", None, _templates_for("newTab")),
    BuiltInGesture("lockScreen", "锁定屏幕", "lockScreen", None, _templates_for("lockScreen")),
    BuiltInGesture("delete", "删除", "delete", None, [_samples("deleteSample")]),
    BuiltInGesture("spaceLeft", "向左切换桌面", "switchSpaceLeft", None, [_samples("spaceLeftSample")]),
    BuiltInGesture("spaceRight", "向右切换桌面", "switchSpaceRight", None, [_samples("spaceRightSample")]),
    BuiltInGesture("close", "关闭", "close", None, [_samples("closeUserDrawn"), _samples("closeSimple")]),
]

BUILT_IN_BY_ID = {item.id: item for item in BUILT_INS}
BUILT_IN_BY_ACTION = {item.action: item for item in BUILT_INS}


@dataclass(frozen=True)
class ActionShortcut:
    vk: int
    modifiers: int
    display: str
    special: str | None = None


def action_shortcut(action: str) -> ActionShortcut | None:
    """Return the Windows keystroke used for a built-in action.

    `special` is used for actions that should call a Win32 API instead of
    synthesising a keystroke.
    """
    if action == "back":
        return ActionShortcut(VK_LEFT, MOD_ALT, "Alt+←")
    if action == "forward":
        return ActionShortcut(VK_RIGHT, MOD_ALT, "Alt+→")
    if action == "missionControl":
        return ActionShortcut(0x09, MOD_WIN, "Win+Tab")  # VK_TAB
    if action == "appExpose":
        return ActionShortcut(0x09, MOD_WIN, "Win+Tab")
    if action == "undo":
        return ActionShortcut(0x5A, MOD_CONTROL, "Ctrl+Z")
    if action == "copy":
        return ActionShortcut(0x43, MOD_CONTROL, "Ctrl+C")
    if action == "paste":
        return ActionShortcut(0x56, MOD_CONTROL, "Ctrl+V")
    if action == "newTab":
        return ActionShortcut(0x54, MOD_CONTROL, "Ctrl+T")
    if action == "delete":
        return ActionShortcut(VK_DELETE, 0, "Delete")
    if action == "switchSpaceLeft":
        return ActionShortcut(VK_LEFT, MOD_CONTROL | MOD_WIN, "Ctrl+Win+←")
    if action == "switchSpaceRight":
        return ActionShortcut(VK_RIGHT, MOD_CONTROL | MOD_WIN, "Ctrl+Win+→")
    if action == "lockScreen":
        return ActionShortcut(0, 0, "锁定屏幕", special="lockScreen")
    return None


def swipe_symbol(direction: str | None) -> str:
    return {
        "left": "←",
        "right": "→",
        "up": "↑",
        "down": "↓",
    }.get(direction or "", "")


def find_builtin(identifier: str) -> BuiltInGesture | None:
    return BUILT_IN_BY_ID.get(identifier)

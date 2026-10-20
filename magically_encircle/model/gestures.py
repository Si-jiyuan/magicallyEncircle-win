"""Gesture data model and persistence.

The Swift app encodes coordinates as AppKit global coordinates (y grows up).
The Windows app works in screen coordinates (y grows down) internally.  All
import/export paths therefore convert explicitly; see `to_dict`/`from_dict`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Iterable

from ..config import (
    BUILTIN_SHORTCUTS_FILE,
    GESTURES_FILE,
    OVERRIDES_FILE,
    atomic_write_json,
    read_json,
)

Point = tuple[float, float]
Stroke = list[Point]
Strokes = list[Stroke]

CoordinateSystem = str
COORDS_APPKIT = "appkit-y-up"
COORDS_SCREEN = "screen-y-down"


def flip_y(strokes: Iterable[Iterable[Point]]) -> Strokes:
    return [[(float(x), -float(y)) for x, y in stroke] for stroke in strokes]


def points_to_json(stroke: Iterable[Point], y_up: bool) -> list[dict[str, float]]:
    return [{"x": float(x), "y": float(-y if y_up else y)} for x, y in stroke]


def points_from_json(points: Any, y_up: bool) -> Stroke:
    result: Stroke = []
    if not isinstance(points, list):
        return result
    for item in points:
        if not isinstance(item, dict):
            continue
        try:
            x = float(item.get("x", 0.0))
            y = float(item.get("y", 0.0))
        except (TypeError, ValueError):
            continue
        result.append((x, -y if y_up else y))
    return result


def strokes_to_json(strokes: Iterable[Iterable[Point]], y_up: bool) -> list[list[dict[str, float]]]:
    return [points_to_json(stroke, y_up) for stroke in strokes]


def strokes_from_json(strokes: Any, y_up: bool) -> Strokes:
    if not isinstance(strokes, list):
        return []
    return [points_from_json(stroke, y_up) for stroke in strokes]


@dataclass
class CustomGesture:
    id: str
    name: str
    strokes: Strokes
    key_code: int | None = None
    modifier_flags: int = 0
    key_display: str = ""
    app_paths: list[str] | None = None
    imported_display: str = ""

    @classmethod
    def new(cls, name: str, strokes: Strokes) -> "CustomGesture":
        return cls(id=str(uuid.uuid4()), name=name, strokes=strokes)

    @property
    def is_shortcut_bound(self) -> bool:
        return self.key_code is not None

    @property
    def is_app_bound(self) -> bool:
        return bool(self.app_paths)

    @property
    def is_bound(self) -> bool:
        return self.is_shortcut_bound or self.is_app_bound

    @property
    def menu_title(self) -> str:
        if self.key_display:
            return f"{self.name}（{self.key_display}）"
        if self.is_app_bound:
            return f"{self.name}（App）"
        return self.name

    def to_dict(self, y_up: bool) -> dict[str, Any]:
        strokes = [stroke for stroke in self.strokes if len(stroke) >= 1]
        first = strokes[0] if strokes else []
        multi = strokes if len(strokes) > 1 else None
        data: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "keyCode": self.key_code,
            "modifierFlags": int(self.modifier_flags) if self.key_code is not None else 0,
            "keyDisplay": self.key_display,
            "appBundleIDs": list(self.app_paths) if self.app_paths else None,
            "points": points_to_json(first, y_up),
            "multiStrokes": strokes_to_json(multi, y_up) if multi else None,
        }
        if self.imported_display:
            data["sourceKeyDisplay"] = self.imported_display
        return data

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        source_platform: str = "windows",
        coordinate_system: str = COORDS_SCREEN,
    ) -> "CustomGesture | None":
        if not isinstance(data, dict):
            return None
        name = str(data.get("name") or "图案")
        raw_multi = data.get("multiStrokes")
        y_up = coordinate_system != COORDS_SCREEN
        if isinstance(raw_multi, list) and raw_multi:
            strokes = strokes_from_json(raw_multi, y_up)
        else:
            strokes = [points_from_json(data.get("points"), y_up)]
        strokes = [stroke for stroke in strokes if len(stroke) >= 1]
        if not strokes:
            return None

        windows_package = source_platform == "windows"
        key_code: int | None = None
        modifiers = 0
        key_display = ""
        app_paths: list[str] | None = None
        imported_display = str(data.get("sourceKeyDisplay") or "")

        if windows_package:
            try:
                if data.get("keyCode") is not None:
                    key_code = int(data["keyCode"])
                modifiers = int(data.get("modifierFlags") or 0)
            except (TypeError, ValueError):
                key_code = None
                modifiers = 0
            key_display = str(data.get("keyDisplay") or "")
            raw_apps = data.get("appBundleIDs")
            if isinstance(raw_apps, list):
                app_paths = [str(item) for item in raw_apps if item]
        else:
            # macOS virtual key codes and bundle ids are meaningless here.
            imported_display = str(data.get("keyDisplay") or "")

        return cls(
            id=str(data.get("id") or uuid.uuid4()),
            name=name,
            strokes=strokes,
            key_code=key_code,
            modifier_flags=modifiers,
            key_display=key_display,
            app_paths=app_paths,
            imported_display=imported_display,
        )


@dataclass
class BuiltInShortcut:
    key_code: int
    modifier_flags: int
    key_display: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "keyCode": int(self.key_code),
            "modifierFlags": int(self.modifier_flags),
            "keyDisplay": self.key_display,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "BuiltInShortcut | None":
        if not isinstance(data, dict) or data.get("keyCode") is None:
            return None
        try:
            return cls(
                key_code=int(data["keyCode"]),
                modifier_flags=int(data.get("modifierFlags") or 0),
                key_display=str(data.get("keyDisplay") or ""),
            )
        except (TypeError, ValueError):
            return None


class CustomGestureStore:
    def load(self) -> list[CustomGesture]:
        raw = read_json(GESTURES_FILE, [])
        if not isinstance(raw, list):
            return []
        result: list[CustomGesture] = []
        for item in raw:
            gesture = CustomGesture.from_dict(
                item,
                source_platform=str(item.get("_sourcePlatform") or "windows") if isinstance(item, dict) else "windows",
                coordinate_system=COORDS_SCREEN,
            )
            if gesture is not None:
                result.append(gesture)
        return result

    def save(self, gestures: list[CustomGesture]) -> None:
        atomic_write_json(GESTURES_FILE, [gesture.to_dict(y_up=False) for gesture in gestures])


class GestureOverrideStore:
    """Maps a built-in gesture id to a list of user-drawn samples.

    Each sample is a list of strokes; each stroke is a list of (x, y) points.
    """

    def load(self) -> dict[str, list[Strokes]]:
        raw = read_json(OVERRIDES_FILE, {})
        if not isinstance(raw, dict):
            return {}
        result: dict[str, list[Strokes]] = {}
        for key, samples in raw.items():
            if not isinstance(samples, list):
                continue
            converted: list[Strokes] = []
            for sample in samples:
                converted.append(strokes_from_json(sample, y_up=False))
            result[str(key)] = converted
        return result

    def save(self, overrides: dict[str, list[Strokes]]) -> None:
        data: dict[str, Any] = {}
        for key, samples in overrides.items():
            data[key] = [strokes_to_json(sample, y_up=False) for sample in samples]
        atomic_write_json(OVERRIDES_FILE, data)


class BuiltInShortcutStore:
    def load(self) -> dict[str, BuiltInShortcut]:
        raw = read_json(BUILTIN_SHORTCUTS_FILE, {})
        if not isinstance(raw, dict):
            return {}
        result: dict[str, BuiltInShortcut] = {}
        for key, value in raw.items():
            shortcut = BuiltInShortcut.from_dict(value)
            if shortcut is not None:
                result[str(key)] = shortcut
        return result

    def save(self, shortcuts: dict[str, BuiltInShortcut]) -> None:
        atomic_write_json(BUILTIN_SHORTCUTS_FILE, {key: value.to_dict() for key, value in shortcuts.items()})

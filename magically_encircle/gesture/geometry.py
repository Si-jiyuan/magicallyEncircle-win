"""Geometry helpers ported from the macOS app.

All points are (x, y) in Windows screen coordinates (y grows down).
"""

from __future__ import annotations

import math

from ..model.gestures import Point, Stroke


def distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def path_length(points: Stroke) -> float:
    if len(points) < 2:
        return 0.0
    total = 0.0
    for index in range(1, len(points)):
        total += distance(points[index - 1], points[index])
    return total


def bounding_box(points: Stroke) -> tuple[float, float, float, float]:
    """Return (min_x, min_y, width, height)."""
    if not points:
        return (0.0, 0.0, 0.0, 0.0)
    min_x = max_x = points[0][0]
    min_y = max_y = points[0][1]
    for x, y in points:
        min_x = min(min_x, x)
        max_x = max(max_x, x)
        min_y = min(min_y, y)
        max_y = max(max_y, y)
    return (min_x, min_y, max_x - min_x, max_y - min_y)


def polygon_area(points: Stroke) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    j = len(points) - 1
    for i in range(len(points)):
        area += (points[j][0] + points[i][0]) * (points[j][1] - points[i][1])
        j = i
    return abs(area / 2.0)


def is_closed_loop(points: Stroke) -> bool:
    if len(points) <= 6:
        return False
    _, _, width, height = bounding_box(points)
    diagonal = math.hypot(width, height)
    if diagonal <= 60:
        return False
    if distance(points[0], points[-1]) >= 0.35 * diagonal:
        return False
    if polygon_area(points) <= 0.06 * diagonal * diagonal:
        return False
    if path_length(points) <= 1.4 * diagonal:
        return False
    return True


def swipe_direction(points: Stroke) -> str | None:
    """Return 'left'/'right'/'up'/'down' for a nearly straight stroke."""
    length = path_length(points)
    if length <= 60 or not points:
        return None
    straight = distance(points[0], points[-1])
    if straight / length <= 0.8:
        return None
    dx = points[-1][0] - points[0][0]
    dy = points[-1][1] - points[0][1]
    if abs(dx) >= abs(dy):
        return "right" if dx >= 0 else "left"
    # Windows y grows down, the opposite of AppKit.
    return "down" if dy >= 0 else "up"

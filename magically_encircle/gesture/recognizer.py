"""$1 Unistroke Recognizer with multi-stroke matching.

Ported from `Gesture/GestureRecognizer.swift`.  The math is intentionally kept
identical so the same templates and thresholds behave the same way.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..constants import SAMPLE_COUNT, SQUARE_SIZE
from ..model.gestures import Point, Stroke, Strokes
from . import geometry


@dataclass
class GestureCandidate:
    name: str
    strokes: Strokes
    action: str | None = None
    custom_id: str | None = None


class GestureRecognizer:
    def __init__(self, sample_count: int = SAMPLE_COUNT, square_size: float = SQUARE_SIZE) -> None:
        self.sample_count = sample_count
        self.square_size = square_size

    def recognize(self, strokes: Strokes, candidates: list[GestureCandidate]):
        ranked = self.ranked(strokes, candidates)
        return ranked[0] if ranked else None

    def ranked(self, strokes: Strokes, candidates: list[GestureCandidate]):
        if not strokes or not candidates:
            return []
        result = []
        for candidate in candidates:
            score = self.match_strokes(strokes, candidate.strokes)
            result.append((candidate, score))
        result.sort(key=lambda item: item[1], reverse=True)
        return result

    def match_strokes(self, a: Strokes, b: Strokes) -> float:
        strokes_a = [stroke for stroke in a if len(stroke) >= 2 and geometry.path_length(stroke) > 0]
        strokes_b = [stroke for stroke in b if len(stroke) >= 2 and geometry.path_length(stroke) > 0]
        if not strokes_a or not strokes_b:
            return 0.0
        if len(strokes_a) == 1 and len(strokes_b) == 1:
            return self.single_stroke_score(strokes_a[0], strokes_b[0])

        shape = self.greedy_stroke_score(strokes_a, strokes_b)
        arrangement = self.cloud_score(strokes_a, strokes_b)
        # The overall arrangement matters more; this avoids confusing two
        # separate slashes with a crossed X.
        return shape * 0.35 + arrangement * 0.65

    def greedy_stroke_score(self, strokes_a: Strokes, strokes_b: Strokes) -> float:
        used = [False] * len(strokes_b)
        total = 0.0
        for stroke in strokes_a:
            best = 0.0
            best_index = -1
            for index, other in enumerate(strokes_b):
                if used[index]:
                    continue
                score = self.single_stroke_score(stroke, other)
                if score > best:
                    best = score
                    best_index = index
            if best_index >= 0:
                used[best_index] = True
                total += best
        return total / float(max(len(strokes_a), len(strokes_b)))

    def cloud_score(self, strokes_a: Strokes, strokes_b: Strokes) -> float:
        cloud_a = self.cloud_points(strokes_a, per_stroke=self.sample_count // 2)
        cloud_b = self.cloud_points(strokes_b, per_stroke=self.sample_count // 2)
        if not cloud_a or not cloud_b:
            return 0.0

        normalized_a = self.translate_to_origin(self.scale_to_square(cloud_a, self.square_size))
        normalized_b = self.translate_to_origin(self.scale_to_square(cloud_b, self.square_size))

        forward = self.greedy_cloud_distance(normalized_a, normalized_b)
        backward = self.greedy_cloud_distance(normalized_b, normalized_a)
        return (forward + backward) / 2.0

    @staticmethod
    def cloud_points(strokes: Strokes, per_stroke: int) -> Stroke:
        points: Stroke = []
        for stroke in strokes:
            if len(stroke) >= 2:
                points.extend(GestureRecognizer.resample(stroke, max(2, per_stroke)))
        return points

    def greedy_cloud_distance(self, a: Stroke, b: Stroke) -> float:
        if not a or not b:
            return 0.0
        used = [False] * len(b)
        total = 0.0
        matched = 0
        for point in a:
            best = math.inf
            best_index = -1
            for index, other in enumerate(b):
                if used[index]:
                    continue
                dist = geometry.distance(point, other)
                if dist < best:
                    best = dist
                    best_index = index
            if best_index >= 0:
                used[best_index] = True
                total += best
                matched += 1
        if matched == 0:
            return 0.0
        average = total / matched
        half_diagonal = 0.5 * math.hypot(self.square_size, self.square_size)
        return max(0.0, 1.0 - float(average / half_diagonal))

    def single_stroke_score(self, a: Stroke, b: Stroke) -> float:
        if len(a) < 2 or len(b) < 2:
            return 0.0
        processed_a = self.preprocess(a)
        processed_b = self.preprocess(b)
        return self.best_rotated_score(processed_a, processed_b)

    def best_rotated_score(self, candidate: Stroke, template: Stroke) -> float:
        variants = [candidate, list(reversed(candidate))]
        best = 0.0
        for variant in variants:
            for angle in (-10.0, 0.0, 10.0):
                rotated = self.translate_to_origin(self.rotate(variant, angle))
                best = max(best, self.score(rotated, template))
        return best

    def preprocess(self, raw: Stroke) -> Stroke:
        resampled = self.resample(raw, self.sample_count)
        scaled = self.scale_to_square(resampled, self.square_size)
        return self.translate_to_origin(scaled)

    @staticmethod
    def resample(points: Stroke, count: int) -> Stroke:
        if len(points) <= 1:
            return list(points)
        interval = geometry.path_length(points) / float(count - 1)
        if interval <= 0:
            return list(points)

        working = list(points)
        accumulated = 0.0
        result: Stroke = [points[0]]
        index = 1

        while index < len(working):
            dist = geometry.distance(working[index - 1], working[index])
            if dist <= 0:
                index += 1
                continue
            if accumulated + dist >= interval:
                t = (interval - accumulated) / dist
                point = (
                    working[index - 1][0] + t * (working[index][0] - working[index - 1][0]),
                    working[index - 1][1] + t * (working[index][1] - working[index - 1][1]),
                )
                result.append(point)
                working.insert(index, point)
                accumulated = 0.0
            else:
                accumulated += dist
            index += 1

        while len(result) < count and points:
            result.append(points[-1])
        if len(result) > count:
            result = result[:count]
        return result

    @staticmethod
    def scale_to_square(points: Stroke, size: float) -> Stroke:
        min_x, min_y, width, height = geometry.bounding_box(points)
        side = max(width, height)
        if side <= 0:
            return list(points)
        scale = size / side
        return [((x - min_x) * scale, (y - min_y) * scale) for x, y in points]

    @staticmethod
    def translate_to_origin(points: Stroke) -> Stroke:
        if not points:
            return []
        sum_x = sum(point[0] for point in points)
        sum_y = sum(point[1] for point in points)
        cx = sum_x / len(points)
        cy = sum_y / len(points)
        return [(x - cx, y - cy) for x, y in points]

    def score(self, a: Stroke, b: Stroke) -> float:
        if len(a) != len(b) or not a:
            return 0.0
        total = sum(geometry.distance(a[index], b[index]) for index in range(len(a)))
        average = total / len(a)
        half_diagonal = 0.5 * math.hypot(self.square_size, self.square_size)
        return max(0.0, 1.0 - float(average / half_diagonal))

    @staticmethod
    def rotate(points: Stroke, degrees: float) -> Stroke:
        radians = math.radians(degrees)
        cos_value = math.cos(radians)
        sin_value = math.sin(radians)
        return [
            (x * cos_value - y * sin_value, x * sin_value + y * cos_value)
            for x, y in points
        ]


recognizer = GestureRecognizer()

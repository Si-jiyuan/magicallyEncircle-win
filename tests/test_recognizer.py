from __future__ import annotations

import math
import unittest

from magically_encircle.gesture import geometry
from magically_encircle.gesture.builtin import BUILT_INS
from magically_encircle.gesture.recognizer import GestureCandidate, recognizer
from magically_encircle.gesture.templates_data import TEMPLATES, USER_DRAWN_SAMPLES


def all_candidates() -> list[GestureCandidate]:
    result: list[GestureCandidate] = []
    for built_in in BUILT_INS:
        for sample in built_in.default_samples:
            result.append(GestureCandidate(built_in.title, sample, built_in.action))
    return result


class RecognizerTests(unittest.TestCase):
    def test_templates_recognise_themselves(self) -> None:
        candidates = all_candidates()
        for entry in TEMPLATES:
            strokes = [entry["points"]]
            ranked = recognizer.ranked(strokes, candidates)
            self.assertTrue(ranked, entry["name"])
            self.assertEqual(ranked[0][0].action, entry["action"], entry["name"])
            self.assertGreaterEqual(ranked[0][1], 0.9, entry["name"])

    def test_user_drawn_samples_recognise_themselves(self) -> None:
        candidates = all_candidates()
        for name in ("deleteSample", "spaceLeftSample", "spaceRightSample"):
            strokes = USER_DRAWN_SAMPLES[name]
            ranked = recognizer.ranked(strokes, candidates)
            self.assertTrue(ranked, name)
            self.assertGreaterEqual(ranked[0][1], 0.85, name)

    def test_reverse_drawing_still_matches(self) -> None:
        candidates = all_candidates()
        for entry in TEMPLATES[:3]:
            strokes = [list(reversed(entry["points"]))]
            ranked = recognizer.ranked(strokes, candidates)
            self.assertEqual(ranked[0][0].action, entry["action"], entry["name"])

    def test_small_rotation_still_matches(self) -> None:
        candidates = all_candidates()
        entry = TEMPLATES[0]
        rotated = [
            (
                x * math.cos(math.radians(8)) - y * math.sin(math.radians(8)),
                x * math.sin(math.radians(8)) + y * math.cos(math.radians(8)),
            )
            for x, y in entry["points"]
        ]
        ranked = recognizer.ranked([rotated], candidates)
        self.assertEqual(ranked[0][0].action, entry["action"])

    def test_cross_is_multi_stroke(self) -> None:
        candidates = all_candidates()
        ranked = recognizer.ranked(USER_DRAWN_SAMPLES["closeSimple"], candidates)
        self.assertEqual(ranked[0][0].action, "close")

    def test_swipe_direction_y_down(self) -> None:
        self.assertEqual(geometry.swipe_direction([(0, 0), (200, 0)]), "right")
        self.assertEqual(geometry.swipe_direction([(200, 0), (0, 0)]), "left")
        self.assertEqual(geometry.swipe_direction([(0, 0), (0, 200)]), "down")
        self.assertEqual(geometry.swipe_direction([(0, 200), (0, 0)]), "up")
        self.assertIsNone(geometry.swipe_direction([(0, 0), (10, 0)]))

    def test_closed_loop(self) -> None:
        circle = [
            (100 + 70 * math.cos(math.tau * i / 40), 100 + 70 * math.sin(math.tau * i / 40))
            for i in range(41)
        ]
        self.assertTrue(geometry.is_closed_loop(circle))
        self.assertFalse(geometry.is_closed_loop([(0, 0), (100, 0)]))

    def test_parallel_slashes_are_not_a_cross(self) -> None:
        candidates = all_candidates()
        two_slashes = [[(0, 0), (80, 80)], [(40, 0), (120, 80)]]
        ranked = recognizer.ranked(two_slashes, candidates)
        cross_score = recognizer.ranked(USER_DRAWN_SAMPLES["closeSimple"], candidates)[0][1]
        self.assertLess(ranked[0][1], cross_score)


if __name__ == "__main__":
    unittest.main()

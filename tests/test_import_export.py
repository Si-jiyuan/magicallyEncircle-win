from __future__ import annotations

import unittest

from magically_encircle.model.gestures import (
    COORDS_APPKIT,
    COORDS_SCREEN,
    CustomGesture,
    flip_y,
    strokes_from_json,
    strokes_to_json,
)


class ImportExportTests(unittest.TestCase):
    def test_windows_roundtrip(self) -> None:
        gesture = CustomGesture.new("test", [[(10.0, 20.0), (30.0, 40.0)], [(50.0, 60.0), (70.0, 80.0)]])
        gesture.key_code = 0x43
        gesture.modifier_flags = 2
        gesture.key_display = "Ctrl+C"

        payload = gesture.to_dict(y_up=True)
        restored = CustomGesture.from_dict(payload, "windows", COORDS_APPKIT)
        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(restored.strokes, gesture.strokes)
        self.assertEqual(restored.key_code, 0x43)
        self.assertEqual(restored.key_display, "Ctrl+C")
        self.assertEqual(restored.name, "test")

    def test_macos_package_drops_platform_specific_bindings(self) -> None:
        payload = {
            "id": "abc",
            "name": "mac",
            "keyCode": 8,
            "modifierFlags": 0x100000,
            "keyDisplay": "⌘C",
            "appBundleIDs": ["com.apple.Safari"],
            "points": [{"x": 1.0, "y": 2.0}, {"x": 3.0, "y": 4.0}],
            "multiStrokes": None,
        }
        restored = CustomGesture.from_dict(payload, "macos", COORDS_APPKIT)
        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertIsNone(restored.key_code)
        self.assertFalse(restored.is_app_bound)
        self.assertEqual(restored.imported_display, "⌘C")
        # AppKit y-up -> internal y-down.
        self.assertEqual(restored.strokes, [[(1.0, -2.0), (3.0, -4.0)]])

    def test_internal_storage_is_y_down(self) -> None:
        gesture = CustomGesture.new("test", [[(1.0, -2.0), (3.0, -4.0)]])
        payload = gesture.to_dict(y_up=False)
        self.assertEqual(payload["points"][0]["y"], -2.0)
        restored = CustomGesture.from_dict(payload, "windows", COORDS_SCREEN)
        self.assertEqual(restored.strokes, gesture.strokes)

    def test_override_sample_roundtrip(self) -> None:
        sample = [[(1.0, 2.0), (3.0, 4.0)], [(5.0, 6.0), (7.0, 8.0)]]
        payload = strokes_to_json(sample, y_up=True)
        self.assertEqual(payload[0][0]["y"], -2.0)
        restored = strokes_from_json(payload, y_up=True)
        self.assertEqual(restored, sample)

    def test_flip_y(self) -> None:
        self.assertEqual(flip_y([[(1.0, 2.0)]]), [[(1.0, -2.0)]])


if __name__ == "__main__":
    unittest.main()

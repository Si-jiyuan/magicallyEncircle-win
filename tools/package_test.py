"""Round-trip test for the export/import package (including macOS data)."""

from __future__ import annotations

import json
import os
import tempfile

os.environ["MAGICALLY_ENCIRCLE_DATA_DIR"] = tempfile.mkdtemp(prefix="magically-test-")

from PySide6.QtWidgets import QApplication

from magically_encircle.config import Settings
from magically_encircle.controller import MagicController
from magically_encircle.model.gestures import CustomGesture
from magically_encircle.platform_support import win32
from magically_encircle.ui.theme import apply_theme


def main() -> int:
    win32.set_dpi_awareness()
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    controller = MagicController(app, Settings())
    controller._desktop_timer.stop()

    gesture = CustomGesture.new("test-gesture", [[(10.0, 20.0), (30.0, 40.0)], [(50.0, 60.0), (70.0, 80.0)]])
    gesture.key_code = 0x43
    gesture.modifier_flags = 0x0002
    gesture.key_display = "Ctrl+C"
    controller.custom_gestures.append(gesture)
    controller.gesture_overrides["undo"] = [[[(1.0, 2.0), (3.0, 4.0)]]]

    package = controller.build_export_package()
    json.dumps(package)  # must be fully JSON serialisable
    print("package keys:", sorted(package), flush=True)
    print("override:", package["builtInOverrides"], flush=True)
    assert package["platform"] == "windows"
    assert package["coordinateSystem"] == "appkit-y-up"
    assert package["gestures"][0]["points"][0]["y"] == -20.0
    assert package["builtInOverrides"]["undo"][0][0][0]["y"] == -2.0

    controller.custom_gestures.clear()
    controller.gesture_overrides.clear()
    count = controller.import_package(package)
    print("windows import:", count, controller.custom_gestures[0].key_display, flush=True)
    assert count == 2
    assert controller.custom_gestures[0].strokes == gesture.strokes
    assert controller.custom_gestures[0].key_code == 0x43
    assert controller.gesture_overrides["undo"][0] == [[(1.0, 2.0), (3.0, 4.0)]]

    # Simulate a macOS package.  Coordinates are already AppKit y-up.
    mac_package = json.loads(json.dumps(package))
    mac_package["platform"] = "macos"
    mac_package["gestures"][0]["keyCode"] = 8
    mac_package["gestures"][0]["modifierFlags"] = 0x100000
    mac_package["gestures"][0]["keyDisplay"] = "Cmd+C"
    mac_package["gestures"][0]["appBundleIDs"] = ["com.apple.Safari"]
    controller.custom_gestures.clear()
    controller.gesture_overrides.clear()
    count = controller.import_package(mac_package)
    imported = controller.custom_gestures[0]
    print("mac import:", count, imported.key_code, repr(imported.key_display), repr(imported.imported_display), imported.app_paths, flush=True)
    assert count == 2
    assert imported.key_code is None
    assert imported.key_display == ""
    assert imported.imported_display == "Cmd+C"
    assert imported.app_paths is None
    assert imported.strokes == gesture.strokes

    controller.shutdown()
    app.exit(0)
    print("package test OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

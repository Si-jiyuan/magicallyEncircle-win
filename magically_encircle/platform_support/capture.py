"""Screen capture and clipboard image conversion."""

from __future__ import annotations

import logging
from PIL import Image, ImageGrab
from PySide6.QtGui import QImage

log = logging.getLogger(__name__)


def capture_physical_bbox(bbox: tuple[int, int, int, int]) -> Image.Image | None:
    left, top, right, bottom = bbox
    if right - left < 2 or bottom - top < 2:
        return None
    try:
        return ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)
    except Exception:
        log.exception("Screen capture failed")
        return None


def pil_to_qimage(image: Image.Image) -> QImage:
    rgba = image.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimage = QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format_RGBA8888)
    return qimage.copy()

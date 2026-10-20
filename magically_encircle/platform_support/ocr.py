"""Text recognition through the Windows Runtime OCR engine.

The WinRT projection is imported lazily so the rest of the app still works if
the optional OCR packages are missing (for example in a development venv).
"""

from __future__ import annotations

import asyncio
import logging
from PIL import Image

log = logging.getLogger(__name__)


def available() -> bool:
    try:
        import winrt.windows.media.ocr  # noqa: F401
        import winrt.windows.graphics.imaging  # noqa: F401
        import winrt.windows.storage.streams  # noqa: F401

        return True
    except Exception:
        return False


async def _recognize_async(image: Image.Image) -> str | None:
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter

    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        for language_tag in ("zh-Hans", "zh-CN", "en-US"):
            try:
                engine = OcrEngine.try_create_from_language(Language(language_tag))
            except Exception:
                engine = None
            if engine is not None:
                break
    if engine is None:
        log.warning("No Windows OCR language is installed")
        return None

    rgba = image.convert("RGBA")
    width, height = rgba.size
    # SoftwareBitmap BGRA8 is little-endian BGRA.  Pillow writes bytes in the
    # requested raw order.
    data = rgba.tobytes("raw", "BGRA")
    writer = DataWriter()
    writer.write_bytes(data)
    buffer = writer.detach_buffer()
    bitmap = SoftwareBitmap.create_copy_from_buffer(
        buffer, BitmapPixelFormat.BGRA8, width, height
    )
    result = await engine.recognize_async(bitmap)
    lines = [line.text for line in result.lines if line.text]
    text = "\n".join(lines).strip()
    return text or None


def recognize(image: Image.Image) -> str | None:
    if not available():
        return None
    try:
        # Small UI text is recognised much better after a modest upscale.
        width, height = image.size
        if 0 < max(width, height) < 1600:
            image = image.resize((width * 2, height * 2), Image.Resampling.LANCZOS)
        return asyncio.run(_recognize_async(image))
    except Exception:
        log.exception("Windows OCR failed")
        return None

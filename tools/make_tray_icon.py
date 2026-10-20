"""Generate a high-contrast tray icon from the application icon."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "icon.png"
PNG_OUT = ROOT / "assets" / "tray-icon.png"
ICO_OUT = ROOT / "assets" / "tray-icon.ico"


def main() -> None:
    icon = Image.open(SOURCE).convert("RGBA")
    icon = ImageEnhance.Brightness(icon).enhance(1.25)
    icon = ImageEnhance.Contrast(icon).enhance(1.08)
    size = 64
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    # A light rounded frame + orange rim keeps the dark app icon visible on
    # both light and dark Windows taskbars.
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=14, fill=(246, 247, 251, 255))
    draw.rounded_rectangle(
        (1, 1, size - 2, size - 2), radius=13, outline=(255, 140, 31, 255), width=2
    )
    inset = 7
    inner = icon.resize((size - inset * 2, size - inset * 2), Image.Resampling.LANCZOS)
    canvas.alpha_composite(inner, (inset, inset))
    canvas.save(PNG_OUT)
    canvas.save(
        ICO_OUT,
        sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (48, 48), (64, 64)],
    )
    print(PNG_OUT)
    print(ICO_OUT)


if __name__ == "__main__":
    main()

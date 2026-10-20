"""Extract the built-in gesture samples from the macOS Swift sources.

The Swift project stores gesture samples in AppKit coordinates (y grows up).
The Windows app uses screen coordinates (y grows down), so the extracted
coordinates are negated here.  The generated module is checked in so the
Windows build does not need the macOS sources at runtime.
"""

from __future__ import annotations

import re
from pathlib import Path

MAC_ROOT = Path(r"D:\work\projects\magicallyEncircle\magicallyEncircle")
OUT = Path(__file__).resolve().parents[1] / "magically_encircle" / "gesture" / "templates_data.py"

POINT_RE = re.compile(r"CGPoint\(x:\s*(-?\d+(?:\.\d+)?),\s*y:\s*(-?\d+(?:\.\d+)?)\)")


def points(block: str) -> list[tuple[float, float]]:
    result = []
    for x, y in POINT_RE.findall(block):
        result.append((float(x), -float(y)))
    return result


def extract_templates() -> list[dict]:
    text = (MAC_ROOT / "Gesture" / "GestureTemplate.swift").read_text(encoding="utf-8")
    pattern = re.compile(
        r'GestureTemplate\(name:\s*"([^"]+)",\s*action:\s*\.(\w+),\s*points:\s*\[(.*?)\]\)',
        re.S,
    )
    templates = []
    for name, action, block in pattern.findall(text):
        templates.append({"name": name, "action": action, "points": points(block)})
    return templates


def extract_builtin_samples() -> dict[str, list[list[tuple[float, float]]]]:
    text = (MAC_ROOT / "Gesture" / "BuiltInGesture.swift").read_text(encoding="utf-8")
    result: dict[str, list[list[tuple[float, float]]]] = {}

    # Multi-stroke user-drawn samples: one stroke per line inside the outer
    # array.  Split the body into bracketed stroke groups.
    for name, body in re.findall(
        r"private static let (\w+): \[\[CGPoint\]\] = \[(.*?)\n    \]", text, re.S
    ):
        strokes = []
        for stroke_block in re.findall(r"\[((?:CGPoint\([^)]*\),?\s*)+)\]", body):
            strokes.append(points(stroke_block))
        result[name] = strokes
    return result


def main() -> None:
    templates = extract_templates()
    samples = extract_builtin_samples()

    lines = [
        '"""Auto-generated from the macOS Swift sources; do not edit by hand.',
        "",
        "Coordinates are already converted from AppKit (y-up) to Windows",
        "screen coordinates (y-down).",
        '"""',
        "",
        "TEMPLATES = [",
    ]
    for entry in templates:
        lines.append("    {")
        lines.append(f"        'name': {entry['name']!r},")
        lines.append(f"        'action': {entry['action']!r},")
        lines.append(f"        'points': {entry['points']!r},")
        lines.append("    },")
    lines.append("]")
    lines.append("")
    lines.append("USER_DRAWN_SAMPLES = {")
    for name, strokes in samples.items():
        lines.append(f"    {name!r}: {strokes!r},")
    lines.append("}")
    lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT} ({len(templates)} templates, {len(samples)} user-drawn samples)")


if __name__ == "__main__":
    main()

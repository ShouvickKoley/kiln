"""Speech-friendly text. Screen readers and TTS engines stumble on '2.6:1', '#8A7F6D',
'120×28' and quoted-kebab-case layer names; this rewrites them into how a person
would say them, so a voice read-out sounds like a sentence, not a spec sheet."""
from __future__ import annotations

import colorsys
import re

from .color import hex_to_rgb

HUES = [(15, "red"), (40, "orange"), (65, "yellow"), (160, "green"), (195, "teal"), (255, "blue"),
        (290, "purple"), (335, "pink"), (360, "red")]


def color_name(hex_color: str) -> str:
    r, g, b = hex_to_rgb(hex_color)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    shade = "very dark " if l < 0.2 else "dark " if l < 0.38 else "light " if l > 0.72 else "very light " if l > 0.9 else ""
    if l > 0.96:
        return "white"
    if l < 0.06:
        return "black"
    if s < 0.14:
        warmth = "warm " if (r > b + 0.03) else "cool " if (b > r + 0.03) else ""
        return f"{shade}{warmth}grey".strip()
    deg = h * 360
    name = next(n for limit, n in HUES if deg <= limit)
    if name == "orange" and l < 0.45:
        name = "rust orange"
    return f"{shade}{name}".strip()


UNIT_WORDS = {"px": "pixels", "pt": "points", "dp": "density-independent pixels"}


def speakable(text: str) -> str:
    t = text
    t = re.sub(r'"([a-z0-9][a-z0-9\-]*)"', lambda m: "the " + m.group(1).replace("-", " ") + " layer", t)
    t = re.sub(r"#([0-9A-Fa-f]{6})\b", lambda m: "a " + color_name("#" + m.group(1)), t)
    t = re.sub(r"(\d+(?:\.\d+)?):1\b", r"\1 to 1", t)
    t = re.sub(r"(\d+)\s*[×x]\s*(\d+)", r"\1 by \2", t)
    t = re.sub(r"(\d+)(px|pt|dp)\b", lambda m: f"{m.group(1)} {UNIT_WORDS[m.group(2)]}", t)
    t = t.replace("·", ",").replace("→", "to").replace("—", ",").replace("≥", "at least").replace("<", "under")
    t = re.sub(r"\bAA\b", "double A", t)
    t = re.sub(r"\bWCAG\b", "W-CAG", t)
    t = re.sub(r"\bCTA\b", "call to action", t)
    t = re.sub(r"[*_`#]+", "", t)
    t = re.sub(r"\s+", " ", t)
    return re.sub(r"\s+([,.])", r"\1", t).strip()

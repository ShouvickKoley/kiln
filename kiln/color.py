"""Colour maths shared by training and inference (pure Python / numpy, no torch)."""
from __future__ import annotations

import colorsys
import math


def hex_to_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def rgb_to_hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02X}" for c in rgb)


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    r, g, b = hex_to_rgb(hex_color)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a: str, b: str) -> float:
    """WCAG 2.x contrast ratio between two colours."""
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def distance(a: str, b: str) -> float:
    """Cheap perceptual-ish distance in [0, 1] (weighted RGB, 'redmean')."""
    r1, g1, b1 = hex_to_rgb(a)
    r2, g2, b2 = hex_to_rgb(b)
    rm = (r1 + r2) / 2
    d = math.sqrt((2 + rm) * (r1 - r2) ** 2 + 4 * (g1 - g2) ** 2 + (3 - rm) * (b1 - b2) ** 2)
    return d / 3.0


def adjust_lightness(hex_color: str, l: float) -> str:
    r, g, b = hex_to_rgb(hex_color)
    h, _, s = colorsys.rgb_to_hls(r, g, b)
    return rgb_to_hex(colorsys.hls_to_rgb(h, max(0.0, min(1.0, l)), s))


def lightness(hex_color: str) -> float:
    r, g, b = hex_to_rgb(hex_color)
    return colorsys.rgb_to_hls(r, g, b)[1]


def fix_contrast(fg: str, bg: str, target: float, move: str = "fg") -> str:
    """Nudge the lightness of `fg` (or of the colour being moved) until it meets `target` against `bg`.
    Searches both directions and returns the closest passing colour to the original."""
    base_l = lightness(fg)
    best, best_d = None, 9.0
    for direction in (-1, 1):
        l = base_l
        for _ in range(100):
            l += direction * 0.01
            if l < 0 or l > 1:
                break
            cand = adjust_lightness(fg, l)
            if contrast(cand, bg) >= target:
                d = abs(l - base_l)
                if d < best_d:
                    best, best_d = cand, d
                break
    if best is None:
        best = "#FFFFFF" if luminance(bg) < 0.18 else "#111111"
    return best


def hue_shift(hex_color: str, degrees: float, sat: float | None = None) -> str:
    r, g, b = hex_to_rgb(hex_color)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    h = (h + degrees / 360.0) % 1.0
    return rgb_to_hex(colorsys.hls_to_rgb(h, l, s if sat is None else sat))

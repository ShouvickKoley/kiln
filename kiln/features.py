"""Frame -> tensor featuriser. Used identically at training time (PyTorch) and at
inference time (onnxruntime on Vercel), so it must stay numpy-only.

A frame is a dict:
    {id, name, w, h, bg, state?: "empty"|"default", layers: [layer, ...]}
Layers are ordered bottom -> top. A layer is:
    {id, name, role, x, y, w, h, fill?, text?, color?, size?, weight?, radius?}
"""
from __future__ import annotations

import numpy as np

from .color import contrast, distance, luminance

ROLES = [
    "container", "heading", "body", "caption", "button_primary", "button_secondary",
    "link", "input", "image", "icon_button", "nav_item", "divider",
]
INTERACTIVE = {"button_primary", "button_secondary", "link", "input", "icon_button", "nav_item"}
BUTTONS = {"button_primary", "button_secondary"}

ISSUES = [
    "low_contrast",        # text below WCAG AA against what's actually behind it
    "weak_hierarchy",      # primary action doesn't stand apart from secondary ones
    "small_tap_target",    # interactive element under ~44pt
    "small_text",          # body/caption text too small to read comfortably
    "crowded",             # elements touching / overlapping
    "missing_guidance",    # empty state with no explanation or next step
]
ISSUE_LABELS = {
    "low_contrast": "Low contrast",
    "weak_hierarchy": "Weak hierarchy",
    "small_tap_target": "Small tap target",
    "small_text": "Small text",
    "crowded": "Crowded spacing",
    "missing_guidance": "Missing guidance",
}

MAX_LAYERS = 24  # the model's context window, in layers
N_FEATURES = len(ROLES) + 27


def has_text(layer) -> bool:
    return bool(layer.get("text"))


def _contains(outer, inner) -> bool:
    cx, cy = inner["x"] + inner["w"] / 2, inner["y"] + inner["h"] / 2
    return outer["x"] <= cx <= outer["x"] + outer["w"] and outer["y"] <= cy <= outer["y"] + outer["h"]


def background_of(frame, idx: int) -> str:
    """Topmost filled layer beneath layer idx that contains its centre, else frame bg."""
    layers = frame["layers"]
    me = layers[idx]
    for j in range(idx - 1, -1, -1):
        o = layers[j]
        if o.get("fill") and o["role"] in ("container", "image", "button_primary", "button_secondary", "input") and _contains(o, me):
            if o["w"] >= me["w"] and o["h"] >= me["h"]:
                return o["fill"]
    return frame.get("bg", "#FFFFFF")


def text_contrast(frame, idx: int) -> tuple[float, bool]:
    l = frame["layers"][idx]
    bg = l["fill"] if (l.get("fill") and l["role"] in BUTTONS | {"input"}) else background_of(frame, idx)
    ratio = contrast(l.get("color", "#000000"), bg)
    size, weight = l.get("size", 14), l.get("weight", 400)
    large = size >= 18 or (size >= 14 and weight >= 700)
    return ratio, large


def _gap(a, b) -> float:
    dx = max(b["x"] - (a["x"] + a["w"]), a["x"] - (b["x"] + b["w"]), 0)
    dy = max(b["y"] - (a["y"] + a["h"]), a["y"] - (b["y"] + b["h"]), 0)
    if dx == 0 and dy == 0:
        # overlapping or touching: negative gap = overlap depth
        ox = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
        oy = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
        return -min(ox, oy)
    return max(dx, dy) if (dx == 0 or dy == 0) else float(np.hypot(dx, dy))


def _nested(a, b) -> bool:
    """True when one layer sits wholly inside the other (e.g. an image inside a card)."""
    def inside(p, q):
        return p["x"] >= q["x"] and p["y"] >= q["y"] and p["x"] + p["w"] <= q["x"] + q["w"] and p["y"] + p["h"] <= q["y"] + q["h"]
    return inside(a, b) or inside(b, a)


def _is_leaf(l) -> bool:
    return l["role"] not in ("container", "divider")


def select_context(frame) -> tuple[list[int], list[int]]:
    """Choose which layers fit in the context window. Returns (kept, dropped) indices.
    Nothing is dropped silently: callers surface `dropped` to the user."""
    n = len(frame["layers"])
    if n <= MAX_LAYERS:
        return list(range(n)), []

    def prio(i):
        l = frame["layers"][i]
        p = 0
        if l["role"] in INTERACTIVE:
            p += 3
        if has_text(l):
            p += 2
        if l["role"] == "container":
            p += 1
        return (p, l["w"] * l["h"])

    order = sorted(range(n), key=prio, reverse=True)
    kept = sorted(order[:MAX_LAYERS])
    dropped = sorted(order[MAX_LAYERS:])
    return kept, dropped


def featurize(frame) -> tuple[np.ndarray, np.ndarray, list[int], list[int]]:
    """Returns (features [MAX_LAYERS, N_FEATURES] float32, mask [MAX_LAYERS] float32, kept, dropped)."""
    kept, dropped = select_context(frame)
    layers = frame["layers"]
    W, H = float(frame["w"]), float(frame["h"])
    bg = frame.get("bg", "#FFFFFF")

    buttons = [i for i in kept if layers[i]["role"] in BUTTONS]
    primary = next((i for i in kept if layers[i]["role"] == "button_primary"), None)
    long_body = sum(1 for i in kept if layers[i]["role"] in ("body", "caption") and len(layers[i].get("text", "")) > 24)
    is_empty = 1.0 if frame.get("state") == "empty" else 0.0
    n_interactive = sum(1 for i in kept if layers[i]["role"] in INTERACTIVE)
    max_btn_area = max([layers[i]["w"] * layers[i]["h"] for i in buttons], default=1.0)

    X = np.zeros((MAX_LAYERS, N_FEATURES), dtype=np.float32)
    M = np.zeros((MAX_LAYERS,), dtype=np.float32)
    R = len(ROLES)
    for slot, i in enumerate(kept):
        l = layers[i]
        f = X[slot]
        M[slot] = 1.0
        f[ROLES.index(l["role"])] = 1.0
        f[R + 0] = l["x"] / W
        f[R + 1] = l["y"] / H
        f[R + 2] = l["w"] / W
        f[R + 3] = l["h"] / H
        f[R + 4] = min(l["w"], l["h"]) / 64.0
        f[R + 5] = 1.0 if l["role"] in INTERACTIVE else 0.0
        if has_text(l):
            ratio, large = text_contrast(frame, i)
            f[R + 6] = 1.0
            f[R + 7] = ratio / 21.0
            f[R + 8] = np.log(ratio) / np.log(21.0)
            f[R + 9] = 1.0 if large else 0.0
            f[R + 10] = l.get("size", 14) / 32.0
            f[R + 11] = l.get("weight", 400) / 900.0
            f[R + 12] = min(len(l["text"]), 80) / 80.0
            f[R + 13] = (ratio - (3.0 if large else 4.5)) / 4.5  # signed margin to AA
        if l.get("fill"):
            under = background_of(frame, i)
            f[R + 14] = 1.0
            f[R + 15] = luminance(l["fill"])
            f[R + 16] = np.log(contrast(l["fill"], under)) / np.log(21.0)
        # hierarchy features (relative to other buttons)
        if l["role"] in BUTTONS and l.get("fill"):
            others = [j for j in buttons if j != i and layers[j].get("fill")]
            d = min([distance(l["fill"], layers[j]["fill"]) for j in others], default=1.0)
            f[R + 17] = d
            f[R + 18] = (l["w"] * l["h"]) / max_btn_area
            f[R + 19] = len(others) / 4.0
        if primary is not None and l["role"] == "button_secondary" and layers[primary].get("fill") and l.get("fill"):
            f[R + 20] = distance(l["fill"], layers[primary]["fill"])
        # spacing
        gaps = [_gap(l, layers[j]) for j in kept if j != i and _is_leaf(layers[j]) and _is_leaf(l) and not _nested(l, layers[j])]
        g = min(gaps, default=64.0)
        f[R + 21] = np.clip(g, -32, 64) / 32.0
        f[R + 22] = 1.0 if g < 0 else 0.0
        # frame-level context (broadcast)
        f[R + 23] = is_empty
        f[R + 24] = min(long_body, 4) / 4.0
        f[R + 25] = 1.0 if primary is not None else 0.0
        f[R + 26] = min(n_interactive, 8) / 8.0
    return X, M, kept, dropped

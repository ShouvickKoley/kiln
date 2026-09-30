"""Turn findings into concrete, reversible canvas patches.

Kiln proposes; nothing changes on the canvas until a person chooses "Insert".
A patch is a list of ops the frontend applies:
    {"op": "set", "layer": id, "props": {...}}
    {"op": "insert", "after": id, "layer": {...}}
    {"op": "shift", "from_y": y, "dy": n}          # push layers at/after y down
"""
from __future__ import annotations

from .color import contrast, fix_contrast, hue_shift
from .features import BUTTONS, background_of, text_contrast


def _idx(frame, layer_id):
    return next(i for i, l in enumerate(frame["layers"]) if l["id"] == layer_id)


def fix_low_contrast(frame, layer_id):
    i = _idx(frame, layer_id)
    l = frame["layers"][i]
    ratio, large = text_contrast(frame, i)
    target = 3.0 if large else 4.5
    bg = l["fill"] if (l.get("fill") and l["role"] in BUTTONS | {"input"}) else background_of(frame, i)
    new = fix_contrast(l.get("color", "#000000"), bg, target + 0.3)
    return [{"op": "set", "layer": layer_id, "props": {"color": new}}], {"color": new, "newratio": f"{contrast(new, bg):.1f}:1"}


def fix_weak_hierarchy(frame, layer_id, accent=None):
    i = _idx(frame, layer_id)
    accent = accent or frame.get("accent", "#B0552A")
    under = background_of(frame, i)
    fill = accent if contrast(accent, under) >= 3 else fix_contrast(accent, under, 3.0)
    text = "#FFFFFF" if contrast("#FFFFFF", fill) >= 4.5 else fix_contrast("#FFFFFF", fill, 4.5)
    return [{"op": "set", "layer": layer_id, "props": {"fill": fill, "color": text}}], {"color": fill}


def fix_tap_target(frame, layer_id):
    l = frame["layers"][_idx(frame, layer_id)]
    m = 24 if l["role"] == "link" else 44
    props = {}
    if l["h"] < m:
        props["h"] = m
        props["y"] = l["y"] - (m - l["h"]) // 2
    if l["w"] < m and l["role"] != "link":
        props["w"] = m
        props["x"] = l["x"] - (m - l["w"]) // 2
    return [{"op": "set", "layer": layer_id, "props": props}], {}


def fix_small_text(frame, layer_id):
    l = frame["layers"][_idx(frame, layer_id)]
    return [{"op": "set", "layer": layer_id, "props": {"size": 12 if l["role"] == "nav_item" else 14}}], {}


def fix_crowded(frame, layer_id, other_id):
    a = frame["layers"][_idx(frame, layer_id)]
    b = frame["layers"][_idx(frame, other_id)]
    top, bottom = (a, b) if a["y"] <= b["y"] else (b, a)
    dy = top["y"] + top["h"] + 6 - bottom["y"]
    if dy <= 0:
        return [], {}
    return [{"op": "set", "layer": bottom["id"], "props": {"y": bottom["y"] + dy}}], {}


def fix_missing_guidance(frame, layer_id):
    h = frame["layers"][_idx(frame, layer_id)]
    y = h["y"] + h["h"] + 8
    body = {"id": f"{layer_id}-guide", "name": "empty-guidance", "role": "body", "x": h["x"], "y": y, "w": h["w"], "h": 40,
            "text": "Items you add show up here. Start with what's new this week.", "color": "#5B554C", "size": 14}
    return [{"op": "shift", "from_y": y, "dy": 44, "within": layer_id}, {"op": "insert", "after": layer_id, "layer": body}], {}


def patch_for(frame, finding, accent=None):
    kind, lid = finding["issue"], finding["layers"][0]["id"]
    if kind == "low_contrast":
        ops = []
        for l in finding["layers"]:
            ops += fix_low_contrast(frame, l["id"])[0]
        return ops
    if kind == "weak_hierarchy":
        return fix_weak_hierarchy(frame, lid, accent)[0]
    if kind == "small_tap_target":
        return [op for l in finding["layers"] for op in fix_tap_target(frame, l["id"])[0]]
    if kind == "small_text":
        return [op for l in finding["layers"] for op in fix_small_text(frame, l["id"])[0]]
    if kind == "crowded":
        other = finding.get("slots", {}).get("_other_id")
        return fix_crowded(frame, lid, other)[0] if other else []
    if kind == "missing_guidance":
        return fix_missing_guidance(frame, lid)[0]
    return []


def alternates(frame, findings):
    """Three alternative full patches that differ in the choice of primary colour."""
    base = frame.get("accent", "#B0552A")
    options = [("Ember", base), ("Slate", hue_shift(base, 190, 0.35)), ("Ink", "#221F1A")]
    out = []
    for name, accent in options:
        ops = []
        for f in findings:
            if f["issue"] == "weak_hierarchy":
                ops += fix_weak_hierarchy(frame, f["layers"][0]["id"], accent)[0]
            else:
                ops += patch_for(frame, f)
        out.append({"label": f"{name} primary", "swatch": accent, "ops": ops})
    return out

"""Synthetic UI-frame generator + heuristic labeller.

Real design files aren't available for a prototype, so we procedurally generate
mobile frames (forms, lists, empty states, card grids, nav bars), inject the kinds
of mistakes the case study talks about (a CTA that blends in, 2.6:1 text, 36px
tap targets, orphaned empty states), and label each *layer* with a design-review
heuristic. The critic model learns to reproduce those judgements from features,
which is what lets it cite the exact layer responsible.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kiln.color import adjust_lightness, contrast, distance, hue_shift, lightness  # noqa: E402
from kiln.features import (  # noqa: E402
    BUTTONS, INTERACTIVE, ISSUES, MAX_LAYERS, _gap, _is_leaf, _nested, background_of, featurize,
    has_text, select_context, text_contrast,
)

LIGHT_BG = ["#FFFFFF", "#F7F5F0", "#F4F4F5", "#FAFAF7", "#EEF2F6"]
DARK_BG = ["#111315", "#1C1916", "#18181B", "#0F172A"]
ACCENTS = ["#B0552A", "#2563EB", "#0F766E", "#7C3AED", "#BE123C", "#15803D", "#C2410C", "#1D4ED8"]
GREYS_LIGHT = ["#E7E5E4", "#E4DED0", "#E5E7EB", "#D6D3D1"]
WORDS = "Continue Save Next Apply Checkout Browse Shop Start Upload Invite Retry Explore".split()


class Builder:
    def __init__(self, rng: random.Random, w=320, h=560):
        self.r = rng
        self.w, self.h = w, h
        self.dark = rng.random() < 0.2
        self.bg = rng.choice(DARK_BG if self.dark else LIGHT_BG)
        self.ink = "#F4F4F5" if self.dark else rng.choice(["#111111", "#221F1A", "#1F2937"])
        self.muted = "#A1A1AA" if self.dark else rng.choice(["#5B554C", "#52525B", "#4B5563"])
        self.accent = rng.choice(ACCENTS)
        self.surface = adjust_lightness(self.bg, lightness(self.bg) + (0.08 if self.dark else -0.04))
        self.secondary_fill = "#27272A" if self.dark else rng.choice(GREYS_LIGHT)
        self.layers: list[dict] = []
        self.y = 24
        self.pad = rng.choice([16, 20, 24])

    def add(self, role, x, y, w, h, **kw):
        l = {"id": f"l{len(self.layers)}", "name": kw.pop("name", role.replace("_", "-")), "role": role,
             "x": round(x), "y": round(y), "w": round(w), "h": round(h)}
        l.update(kw)
        self.layers.append(l)
        return l

    # --- blocks -------------------------------------------------------------
    def header(self, title, sub=None):
        self.add("heading", self.pad, self.y, self.w - 2 * self.pad, 30, text=title, color=self.ink, size=self.r.choice([20, 22, 24]), weight=700)
        self.y += 38
        if sub:
            self.add("body", self.pad, self.y, self.w - 2 * self.pad, 36, text=sub, color=self.muted, size=14, weight=400)
            self.y += 44

    def button(self, label, primary=True, full=True, h=48):
        w = self.w - 2 * self.pad if full else self.r.choice([120, 136, 150])
        role = "button_primary" if primary else "button_secondary"
        fill = self.accent if primary else self.secondary_fill
        color = "#FFFFFF" if primary else self.r.choice([self.ink, self.ink, self.muted])
        l = self.add(role, self.pad, self.y, w, h, fill=fill, text=label, color=color, size=15, weight=600, radius=10,
                     name="cta-primary" if primary else "cta-secondary")
        self.y += h + 12
        return l

    def input(self, label):
        self.add("caption", self.pad, self.y, 200, 16, text=label, color=self.muted, size=12, weight=500)
        self.y += 20
        self.add("input", self.pad, self.y, self.w - 2 * self.pad, 44, fill=self.surface, text=f"Enter {label.lower()}", color=self.muted, size=14, radius=8)
        self.y += 56

    def list_rows(self, n):
        for k in range(n):
            self.add("container", self.pad, self.y, self.w - 2 * self.pad, 64, fill=self.surface, radius=10, name=f"row-{k+1}")
            self.add("image", self.pad + 10, self.y + 10, 44, 44, fill=adjust_lightness(self.accent, 0.85 if not self.dark else 0.25), radius=8, name=f"thumb-{k+1}")
            self.add("body", self.pad + 64, self.y + 12, 150, 20, text=self.r.choice(["Linen shirt", "Ceramic mug", "Desk lamp", "Notebook set", "Wool throw"]), color=self.ink, size=15, weight=500)
            self.add("caption", self.pad + 64, self.y + 38, 100, 16, text=f"${self.r.randint(12, 180)}.00", color=self.muted, size=13)
            if self.r.random() < 0.6:
                self.add("icon_button", self.w - self.pad - 44, self.y + 10, 44, 44, text="", name=f"remove-{k+1}")
            self.y += 72

    def cards(self, n):
        cw = (self.w - 2 * self.pad - 12) / 2
        for k in range(n):
            cx = self.pad + (k % 2) * (cw + 12)
            if k % 2 == 0 and k:
                self.y += 172
            self.add("container", cx, self.y, cw, 160, fill=self.surface, radius=10, name=f"card-{k+1}")
            self.add("image", cx + 8, self.y + 8, cw - 16, 96, fill=adjust_lightness(self.accent, 0.88 if not self.dark else 0.25), radius=6)
            self.add("body", cx + 8, self.y + 112, cw - 16, 18, text="Product name", color=self.ink, size=14, weight=500)
            self.add("caption", cx + 8, self.y + 134, cw - 16, 16, text="$48", color=self.muted, size=13)
        self.y += 172

    def nav(self, n):
        self.add("container", 0, self.h - 72, self.w, 72, fill=self.surface, name="tab-bar")
        iw = self.w / n
        for k in range(n):
            self.add("nav_item", k * iw + (iw - 48) / 2, self.h - 64, 48, 48, text=["Home", "Search", "Cart", "Profile", "More"][k], color=self.muted, size=12, name=f"tab-{k+1}")

    def section(self, label):
        self.add("caption", self.pad, self.y, 200, 16, text=label.upper(), color=self.muted, size=self.r.choice([11, 12, 12, 13]), weight=600, name="section-label")
        self.y += 24

    def settings_rows(self, n, dividers: bool):
        for k in range(n):
            self.add("container", self.pad, self.y, self.w - 2 * self.pad, 56, fill=self.surface, radius=self.r.choice([0, 8, 10]), name=f"row-{k+1}")
            self.add("body", self.pad + 16, self.y + 17, 180, 22, text=self.r.choice(["Profile", "Addresses", "Payment", "Notifications", "Privacy", "Language"]), color=self.ink, size=15)
            if self.r.random() < 0.4:
                self.add("caption", self.w - self.pad - 110, self.y + 19, 70, 18, text=self.r.choice(["On", "English", "2 saved"]), color=self.muted, size=13)
            self.y += 56
            if dividers and k < n - 1:
                self.add("divider", self.pad + 16, self.y, self.w - 2 * self.pad - 16, 1, fill=self.secondary_fill)
            self.y += self.r.choice([0, 8])

    def empty_state(self, guidance: bool, cta: bool, n_secondary: int):
        self.add("image", (self.w - 140) / 2, self.y + 20, 140, 120, fill=adjust_lightness(self.accent, 0.9 if not self.dark else 0.2), radius=70, name="illustration")
        self.y += 160
        self.add("heading", self.pad, self.y, self.w - 2 * self.pad, 28, text=self.r.choice(["Your cart is empty", "No projects yet", "Nothing here"]), color=self.ink, size=20, weight=700)
        self.y += 36
        if guidance:
            self.add("body", self.pad, self.y, self.w - 2 * self.pad, 40, text="Items you add will show up here. Browse the shop to get started.", color=self.muted, size=14)
            self.y += 52
        for _ in range(n_secondary):
            self.button(self.r.choice(["View saved", "Recently viewed", "Help"]), primary=False, full=True, h=44)
        if cta:
            self.button(self.r.choice(WORDS), primary=True)


def generate_frame(rng: random.Random, idx: int = 0) -> dict:
    b = Builder(rng)
    kind = rng.choice(["form", "list", "empty", "empty", "cards", "checkout", "settings", "settings"])
    state = "default"
    if kind == "form":
        b.header(rng.choice(["Sign in", "Create account", "Shipping"]), "Use the email you signed up with." if rng.random() < .6 else None)
        for lab in rng.sample(["Email", "Password", "Name", "Address", "Phone"], rng.randint(2, 4)):
            b.input(lab)
        b.button(rng.choice(WORDS), True)
        if rng.random() < 0.5:
            b.button("Cancel", False)
        if rng.random() < 0.3:
            b.add("divider", b.pad, b.y, b.w - 2 * b.pad, 1, fill=b.secondary_fill)
            b.y += 16
        if rng.random() < 0.6:
            b.add("link", b.pad, b.y, 140, 22, text="Forgot password?", color=b.accent, size=14, name="link")
            b.y += 30
    elif kind == "list":
        b.header(rng.choice(["Cart", "Orders", "Saved"]))
        b.list_rows(rng.randint(2, 5))
        b.button("Checkout", True)
    elif kind == "settings":
        b.header(rng.choice(["Settings", "Account", "Preferences"]))
        for _ in range(rng.randint(1, 2)):
            if b.y > b.h - 200:
                break
            b.section(rng.choice(["Account", "General", "Privacy"]))
            b.settings_rows(rng.randint(2, 4), dividers=rng.random() < 0.5)
            b.y += 12
        if rng.random() < 0.5 and b.y < b.h - 140:
            b.button("Sign out", False)
    elif kind == "cards":
        b.header("Shop")
        b.cards(rng.choice([2, 4, 6]))
    elif kind == "checkout":
        b.header("Checkout", "Review your order before paying.")
        b.list_rows(rng.randint(1, 3))
        for _ in range(rng.randint(0, 2)):
            b.button(rng.choice(["Add promo code", "Change address"]), False, h=44)
        b.button("Pay now", True)
    else:
        state = "empty"
        b.empty_state(guidance=rng.random() < 0.55, cta=rng.random() < 0.7, n_secondary=rng.randint(0, 3))
    if rng.random() < 0.45 and b.y < b.h - 84:
        b.nav(rng.choice([3, 4, 5]))

    frame = {"id": f"f{idx}", "name": kind, "w": b.w, "h": b.h, "bg": b.bg, "state": state, "layers": b.layers}
    perturb(frame, rng, b)
    return frame


def perturb(frame, rng: random.Random, b: Builder):
    L = frame["layers"]
    texts = [l for l in L if has_text(l)]
    # low contrast text
    if texts and rng.random() < 0.45:
        for l in rng.sample(texts, k=min(len(texts), rng.randint(1, 2))):
            bg = l["fill"] if l["role"] in BUTTONS | {"input"} and l.get("fill") else frame["bg"]
            target_l = lightness(bg) + rng.uniform(-0.28, 0.28)
            l["color"] = adjust_lightness(l.get("color", "#000000"), target_l)
    # weak hierarchy: primary looks like the secondaries (or vanishes into bg)
    prim = [l for l in L if l["role"] == "button_primary"]
    if prim and rng.random() < 0.4:
        p = prim[0]
        mode = rng.random()
        if mode < 0.6:
            p["fill"] = adjust_lightness(b.secondary_fill, lightness(b.secondary_fill) + rng.uniform(-0.05, 0.05))
            if rng.random() < 0.5:
                p["color"] = adjust_lightness(p["fill"], lightness(p["fill"]) - rng.uniform(0.2, 0.5))
        else:
            p["fill"] = adjust_lightness(frame["bg"], lightness(frame["bg"]) + rng.uniform(-0.04, 0.04))
            p["color"] = b.ink
        if rng.random() < 0.4 and not any(l["role"] == "button_secondary" for l in L):
            # add secondaries so hierarchy has something to compete with
            sec_color = rng.choice([b.ink, b.muted])
            for k in range(rng.randint(1, 3)):
                y = p["y"] - 56 * (k + 1)
                L.insert(L.index(p), {"id": f"s{k}{rng.randint(0,999)}", "name": "cta-secondary", "role": "button_secondary",
                                      "x": p["x"], "y": y, "w": p["w"], "h": 44, "fill": b.secondary_fill, "text": "More options",
                                      "color": sec_color, "size": 15, "weight": 600, "radius": 10})
    # tap targets
    inter = [l for l in L if l["role"] in INTERACTIVE]
    if inter and rng.random() < 0.35:
        for l in rng.sample(inter, k=min(len(inter), rng.randint(1, 3))):
            if l["role"] == "link":
                l["h"] = rng.randint(12, 18)
            else:
                l["h"] = rng.randint(24, 40)
                if l["role"] in ("icon_button", "nav_item"):
                    l["w"] = l["h"]
    # small text
    body = [l for l in L if l["role"] in ("body", "caption", "link", "nav_item")]
    if body and rng.random() < 0.3:
        for l in rng.sample(body, k=min(len(body), rng.randint(1, 3))):
            l["size"] = rng.choice([8, 9, 10, 11])
    # crowding
    leaves = [l for l in L if _is_leaf(l)]
    if len(leaves) > 3 and rng.random() < 0.3:
        l = rng.choice(leaves[1:])
        l["y"] -= rng.randint(6, 20)
    # rename ids to be stable & unique
    for i, l in enumerate(L):
        l["id"] = f"l{i}"


# --- heuristic labeller -----------------------------------------------------

def label_frame(frame) -> np.ndarray:
    """Per-layer multi-hot labels [MAX_LAYERS, len(ISSUES)] aligned with featurize()'s kept order."""
    kept, _ = select_context(frame)
    L = frame["layers"]
    Y = np.zeros((MAX_LAYERS, len(ISSUES)), dtype=np.float32)
    buttons = [i for i in kept if L[i]["role"] in BUTTONS]
    long_body = sum(1 for i in kept if L[i]["role"] in ("body", "caption") and len(L[i].get("text", "")) > 24)
    has_primary = any(L[i]["role"] == "button_primary" for i in kept)
    for slot, i in enumerate(kept):
        l = L[i]
        if has_text(l):
            ratio, large = text_contrast(frame, i)
            if ratio < (3.0 if large else 4.5):
                Y[slot, 0] = 1
        if l["role"] == "button_primary" and l.get("fill"):
            others = [j for j in buttons if j != i and L[j].get("fill")]
            under = background_of(frame, i)
            blends = contrast(l["fill"], under) < 1.3
            if others:
                d = min(distance(l["fill"], L[j]["fill"]) for j in others)
                area = l["w"] * l["h"] / max(L[j]["w"] * L[j]["h"] for j in others)
                if d < 0.12 and area < 1.4:
                    Y[slot, 1] = 1
            if blends:
                Y[slot, 1] = 1
        if l["role"] in INTERACTIVE:
            thr = 24 if l["role"] == "link" else 44
            if min(l["w"], l["h"]) < thr:
                Y[slot, 2] = 1
        if l["role"] in ("body", "caption", "link", "nav_item") and has_text(l) and l.get("size", 14) < 12:
            Y[slot, 3] = 1
        if _is_leaf(l):
            for j in kept:
                if j != i and _is_leaf(L[j]) and not _nested(l, L[j]) and _gap(l, L[j]) < 4:
                    Y[slot, 4] = 1
                    break
    if frame.get("state") == "empty" and (long_body == 0 or not has_primary):
        tgt = next((s for s, i in enumerate(kept) if L[i]["role"] == "heading"), 0)
        Y[tgt, 5] = 1
    return Y


def build_dataset(n: int, seed: int = 0):
    rng = random.Random(seed)
    X = np.zeros((n, MAX_LAYERS, featurize({"w": 1, "h": 1, "layers": []})[0].shape[1]), dtype=np.float32)
    M = np.zeros((n, MAX_LAYERS), dtype=np.float32)
    Y = np.zeros((n, MAX_LAYERS, len(ISSUES)), dtype=np.float32)
    for k in range(n):
        f = generate_frame(rng, k)
        X[k], M[k], _, _ = featurize(f)
        Y[k] = label_frame(f)
    return X, M, Y


if __name__ == "__main__":
    X, M, Y = build_dataset(2000, 1)
    frame_pos = (Y.max(1)).mean(0)
    for name, p in zip(ISSUES, frame_pos):
        print(f"{name:18s} {p:.2%} of frames")
    print("avg layers", M.sum(1).mean())

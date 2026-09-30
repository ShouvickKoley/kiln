"""The demo canvas: six hand-built frames, each with the kinds of problems a reviewer
would catch (and one that's clean, so Kiln can show restraint)."""
from __future__ import annotations

import copy

PAPER = "#F7F5F0"
INK = "#221F1A"
SOFT = "#5B554C"
EMBER = "#B0552A"
SURF = "#EDEAE3"
WARM = "#DDD6C8"


def L(id, name, role, x, y, w, h, **kw):
    d = {"id": id, "name": name, "role": role, "x": x, "y": y, "w": w, "h": h}
    d.update(kw)
    return d


def _home():
    layers = [
        L("h1", "greeting", "heading", 20, 28, 280, 30, text="Good morning, Ada", color=INK, size=22, weight=700),
        L("h2", "subhead", "body", 20, 64, 280, 20, text="3 orders arriving this week", color=SOFT, size=14),
        L("h3", "card-orders", "container", 20, 100, 280, 120, fill=SURF, radius=12),
        L("h4", "card-orders-title", "body", 36, 116, 200, 20, text="Track your orders", color=INK, size=15, weight=600),
        L("h5", "card-orders-copy", "caption", 36, 140, 240, 32, text="See where each package is and when it lands.", color=SOFT, size=13),
        L("h6", "card-orders-cta", "button_secondary", 36, 180, 120, 28, fill="#FFFFFF", text="View all", color=INK, size=13, weight=600, radius=8),
        L("h7", "card-deals", "container", 20, 236, 280, 120, fill=SURF, radius=12),
        L("h8", "card-deals-title", "body", 36, 252, 200, 20, text="This week's picks", color=INK, size=15, weight=600),
        L("h9", "card-deals-image", "image", 36, 280, 248, 60, fill="#E8CDB5", radius=8),
        L("h10", "tab-bar", "container", 0, 488, 320, 72, fill="#FFFFFF"),
        L("h11", "tab-home", "nav_item", 22, 500, 36, 36, text="Home", color=EMBER, size=10),
        L("h12", "tab-search", "nav_item", 102, 500, 36, 36, text="Search", color=SOFT, size=10),
        L("h13", "tab-cart", "nav_item", 182, 500, 36, 36, text="Cart", color=SOFT, size=10),
        L("h14", "tab-profile", "nav_item", 262, 500, 36, 36, text="Profile", color=SOFT, size=10),
    ]
    return {"id": "f01", "name": "01 · Home", "w": 320, "h": 560, "bg": PAPER, "state": "default", "accent": EMBER, "layers": layers}


def _signin():
    layers = [
        L("s1", "title", "heading", 24, 40, 272, 32, text="Sign in", color=INK, size=26, weight=700),
        L("s2", "subtitle", "body", 24, 80, 272, 40, text="Use the email you checked out with last time.", color=SOFT, size=14),
        L("s3", "email-label", "caption", 24, 140, 200, 16, text="Email", color=SOFT, size=12, weight=500),
        L("s4", "email-input", "input", 24, 160, 272, 46, fill="#FFFFFF", text="ada@example.com", color=SOFT, size=14, radius=8),
        L("s5", "password-label", "caption", 24, 222, 200, 16, text="Password", color=SOFT, size=12, weight=500),
        L("s6", "password-input", "input", 24, 242, 272, 46, fill="#FFFFFF", text="••••••••", color=SOFT, size=14, radius=8),
        L("s7", "cta-primary", "button_primary", 24, 312, 272, 48, fill=EMBER, text="Continue", color="#FFFFFF", size=15, weight=600, radius=10),
        L("s8", "forgot-link", "link", 24, 376, 120, 16, text="Forgot password?", color="#B9B1A3", size=12),
        L("s9", "divider", "divider", 24, 420, 272, 1, fill=WARM),
        L("s10", "sso-google", "button_secondary", 24, 440, 272, 46, fill=SURF, text="Continue with Google", color=INK, size=15, weight=600, radius=10),
    ]
    return {"id": "f02", "name": "02 · Sign in", "w": 320, "h": 560, "bg": PAPER, "state": "default", "accent": EMBER, "layers": layers}


def _cart():
    layers = [L("c1", "title", "heading", 20, 28, 280, 30, text="Cart (3)", color=INK, size=22, weight=700)]
    items = [("Linen shirt", "$68.00"), ("Ceramic mug", "$24.00"), ("Desk lamp", "$112.00")]
    y = 76
    for k, (name, price) in enumerate(items, 1):
        layers += [
            L(f"c{k}0", f"row-{k}", "container", 20, y, 280, 72, fill="#FFFFFF", radius=12),
            L(f"c{k}1", f"thumb-{k}", "image", 32, y + 12, 48, 48, fill="#E8CDB5", radius=8),
            L(f"c{k}2", f"name-{k}", "body", 92, y + 14, 150, 22, text=name, color=INK, size=15, weight=500),
            # price rides up into the product name: the crowding bug
            L(f"c{k}3", f"price-{k}", "caption", 92, y + 30, 100, 18, text=price, color=SOFT, size=13),
            L(f"c{k}4", f"remove-{k}", "icon_button", 252, y + 14, 44, 44, text=""),
        ]
        y += 84
    layers += [
        L("c90", "subtotal", "body", 20, 348, 180, 22, text="Subtotal  $204.00", color=INK, size=16, weight=600),
        L("c91", "cta-primary", "button_primary", 20, 388, 280, 50, fill=EMBER, text="Check out", color="#FFFFFF", size=16, weight=600, radius=10),
    ]
    return {"id": "f03", "name": "03 · Cart", "w": 320, "h": 560, "bg": PAPER, "state": "default", "accent": EMBER, "layers": layers}


def _checkout_empty():
    layers = [
        L("e1", "card", "container", 20, 24, 280, 472, fill="#FFFFFF", radius=16),
        L("e2", "illustration", "image", 90, 60, 140, 120, fill="#EFE7DA", radius=70),
        L("e3", "empty-title", "heading", 40, 204, 240, 28, text="Your cart is empty", color=INK, size=20, weight=700),
        L("e4", "saved-items", "button_secondary", 40, 256, 240, 44, fill=WARM, text="View saved items", color=SOFT, size=14, weight=600, radius=10),
        L("e5", "recently-viewed", "button_secondary", 40, 308, 240, 44, fill=WARM, text="Recently viewed", color=SOFT, size=14, weight=600, radius=10),
        L("e6", "help", "button_secondary", 40, 360, 240, 44, fill=WARM, text="Get help", color=SOFT, size=14, weight=600, radius=10),
        L("e7", "cta-primary", "button_primary", 40, 424, 240, 48, fill="#D9D1C1", text="Continue shopping", color="#8A7F6D", size=15, weight=600, radius=10),
    ]
    return {"id": "f04", "name": "04 · Checkout, empty state", "w": 320, "h": 560, "bg": PAPER, "state": "empty", "accent": EMBER, "layers": layers}


def _settings():
    layers = [
        L("t1", "title", "heading", 20, 28, 280, 30, text="Settings", color=INK, size=22, weight=700),
        L("t2", "section-account", "caption", 20, 76, 200, 16, text="ACCOUNT", color=SOFT, size=12, weight=600),
    ]
    rows = ["Profile", "Addresses", "Payment methods", "Notifications"]
    y = 100
    for k, name in enumerate(rows, 1):
        layers += [
            L(f"t{k}0", f"row-{name.lower().replace(' ', '-')}", "container", 20, y, 280, 56, fill="#FFFFFF", radius=10),
            L(f"t{k}1", f"label-{k}", "body", 36, y + 17, 180, 22, text=name, color=INK, size=15),
        ]
        y += 64
    layers += [
        L("t90", "sign-out", "button_secondary", 20, 380, 280, 48, fill=SURF, text="Sign out", color="#9C4433", size=15, weight=600, radius=10),
    ]
    return {"id": "f05", "name": "05 · Settings", "w": 320, "h": 560, "bg": PAPER, "state": "default", "accent": EMBER, "layers": layers}


def _grid():
    layers = [
        L("g1", "title", "heading", 16, 24, 180, 30, text="Shop", color=INK, size=22, weight=700),
        L("g2", "filter", "button_secondary", 224, 24, 80, 32, fill=SURF, text="Filter", color=INK, size=13, weight=600, radius=16),
    ]
    cw = 138
    for k in range(6):
        cx = 16 + (k % 2) * (cw + 12)
        cy = 72 + (k // 2) * 136
        layers += [
            L(f"g{k}a", f"card-{k+1}", "container", cx, cy, cw, 124, fill="#FFFFFF", radius=10),
            L(f"g{k}b", f"card-{k+1}-image", "image", cx + 6, cy + 6, cw - 12, 70, fill="#E8CDB5", radius=6),
            L(f"g{k}c", f"card-{k+1}-name", "body", cx + 8, cy + 82, cw - 16, 18, text=["Linen shirt", "Mug", "Lamp", "Throw", "Vase", "Tote"][k], color=INK, size=14, weight=500),
            L(f"g{k}d", f"card-{k+1}-price", "caption", cx + 8, cy + 104, cw - 16, 14, text="$48", color=SOFT, size=13),
        ]
    layers += [L("g90", "tab-bar", "container", 0, 488, 320, 72, fill="#FFFFFF")]
    for k, t in enumerate(["Home", "Search", "Cart", "Profile"]):
        layers.append(L(f"g9{k+1}", f"tab-{t.lower()}", "nav_item", 16 + k * 76, 496, 60, 48, text=t, color=EMBER if k == 0 else SOFT, size=12))
    return {"id": "f06", "name": "06 · Shop grid", "w": 320, "h": 560, "bg": PAPER, "state": "default", "accent": EMBER, "layers": layers}


def sample_frames():
    return copy.deepcopy([_home(), _signin(), _cart(), _checkout_empty(), _settings(), _grid()])

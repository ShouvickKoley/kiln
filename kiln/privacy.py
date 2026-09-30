"""Mask personal identifiers before anything is processed. The critic only needs text
*length* (not content), so masking keeps length and loses nothing the model uses.
Nothing is logged or stored server-side; responses carry Cache-Control: no-store."""
from __future__ import annotations

import copy
import re

PATTERNS = [
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("card", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("phone", re.compile(r"(?<!\w)(?:\+?\d{1,3}[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]?\d{3}[ .-]?\d{4}\b")),
]


def mask(text: str) -> tuple[str, dict]:
    counts: dict[str, int] = {}
    for kind, pat in PATTERNS:
        def sub(m, kind=kind):
            counts[kind] = counts.get(kind, 0) + 1
            return "•" * len(m.group(0))
        text = pat.sub(sub, text)
    return text, counts


def mask_frame(frame: dict) -> tuple[dict, dict]:
    f = copy.deepcopy(frame)
    total: dict[str, int] = {}
    for l in f.get("layers", []):
        if l.get("text"):
            l["text"], c = mask(l["text"])
            for k, v in c.items():
                total[k] = total.get(k, 0) + v
    return f, total

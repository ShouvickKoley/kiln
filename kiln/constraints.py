"""Rules a person sets in plain words ("under 50 words", "don't touch the colours").
Parsed deterministically so Kiln can confirm exactly what it understood, keep the rule
active until it's removed, and report whether each reply honoured it."""
from __future__ import annotations

import re

NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "a single": 1, "single": 1}
ISSUE_WORDS = {
    "low_contrast": r"contrast|legibility|readab\w*",
    "weak_hierarchy": r"hierarchy|cta|primary|buttons?",
    "small_tap_target": r"tap targets?|touch targets?|targets?|hit areas?",
    "small_text": r"text size|font size|type size|small text",
    "crowded": r"spacing|padding|gaps?|crowding",
    "missing_guidance": r"empty state|guidance",
}
ISSUE_SHORT = {"low_contrast": "Contrast", "weak_hierarchy": "Hierarchy", "small_tap_target": "Tap targets",
               "small_text": "Text size", "crowded": "Spacing", "missing_guidance": "Empty state"}


def _n(s: str) -> int:
    return int(s) if s.isdigit() else NUM.get(s, 1)


def parse(message: str) -> tuple[list[dict], bool]:
    """Returns (constraints found in this message, clear_all)."""
    m = message.lower()
    if re.search(r"\b(clear|reset|remove|drop|forget) (all )?(the )?(rules|constraints|limits)\b|\bno more rules\b", m):
        return [], True
    out = []
    w = re.search(r"\b(?:under|less than|fewer than|max(?:imum)?(?: of)?|at most|no more than|within|in|keep it (?:to|under))\s+(\d{1,4})\s+words?\b", m)
    if w:
        n = int(w.group(1))
        out.append({"id": "words", "label": f"Under {n} words", "value": n})
    if re.search(r"\b(one|single|1) (sentence|line)s?( each| per (point|issue|finding))?\b|\bone-liners?\b", m):
        out.append({"id": "one_sentence", "label": "One sentence per point", "value": 1})
    t = re.search(r"\b(?:top|only|just|max(?:imum)?|at most)\s+(\d|one|two|three|four|five)\s+(?:issues?|things|findings|problems|points)\b", m)
    if t:
        n = _n(t.group(1))
        out.append({"id": "top", "label": f"Top {n} issue{'s' if n > 1 else ''}", "value": n})
    if re.search(r"\b(don'?t|do not|never|without|no)\b[\w\s]{0,12}\b(chang\w*|touch\w*|edit\w*|modify\w*)?\s*(the |my |our |any )?(brand )?(colou?rs?|palette|fills?|hues?)\b", m) \
            or re.search(r"\bkeep (the |my |our )?(brand )?(colou?rs?|palette)\b", m):
        out.append({"id": "no_color", "label": "No colour changes", "value": True})
    only = re.search(r"\b(?:only|just)\s+(?:talk about |focus on |look at |check |review )?(?:the )?([a-z ]{3,20}?)(?:\s+issues?)?(?:[.,!?]|$| please| pls| for now)", m)
    if only:
        for issue, pat in ISSUE_WORDS.items():
            if re.fullmatch(rf"(?:{pat})", only.group(1).strip()):
                out.append({"id": "only", "label": f"{ISSUE_SHORT[issue]} only", "value": issue})
                break
    if re.search(r"\b(no jargon|plain (english|language|words)|simple words|keep it simple)\b", m):
        out.append({"id": "plain", "label": "Plain language", "value": True})
    return out, False


def merge(active: list[dict], new: list[dict], clear: bool) -> list[dict]:
    if clear:
        return []
    by_id = {c["id"]: c for c in active}
    for c in new:
        by_id[c["id"]] = c
    return list(by_id.values())

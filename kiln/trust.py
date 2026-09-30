"""Trust layer: where each claim comes from, how sure Kiln is, and where reasonable
people disagree.

Every finding Kiln reports is tagged with:
  basis       standard | convention | judgment      (what kind of claim it is)
  evidence    measured | model                       (how Kiln knows)
  confidence  verified | high | medium | low         (calibrated band)
  perspectives: the other defensible positions, so a guideline is never presented
                as a law when it's actually a convention under debate.
"""
from __future__ import annotations

from .color import contrast, hex_to_rgb

# ---------------------------------------------------------------- APCA (WCAG 3 draft)

def apca_lc(text_hex: str, bg_hex: str) -> float:
    """APCA-W3 0.0.98G lightness contrast (Lc). Draft method, not yet a standard."""
    def y(h):
        r, g, b = hex_to_rgb(h)
        v = 0.2126729 * r ** 2.4 + 0.7151522 * g ** 2.4 + 0.0721750 * b ** 2.4
        return v + (0.022 - v) ** 1.414 if v < 0.022 else v
    yt, yb = y(text_hex), y(bg_hex)
    if abs(yb - yt) < 0.0005:
        return 0.0
    if yb > yt:  # dark text on light bg
        sapc = (yb ** 0.56 - yt ** 0.57) * 1.14
        lc = 0.0 if sapc < 0.1 else sapc - 0.027
    else:
        sapc = (yb ** 0.65 - yt ** 0.62) * 1.14
        lc = 0.0 if sapc > -0.1 else sapc + 0.027
    return round(lc * 100, 1)


# ---------------------------------------------------------------- claim types
BASIS = {
    "low_contrast": ("standard", "WCAG 2.2 · 1.4.3 Contrast (Minimum)"),
    "small_tap_target": ("convention", "44pt target (Apple HIG); WCAG 2.2 AA only requires 24px"),
    "small_text": ("convention", "12px minimum is a Kiln convention; WCAG sets no minimum size"),
    "crowded": ("convention", "4px minimum gap, from the 4/8pt spacing grid"),
    "weak_hierarchy": ("judgment", "Design judgment: one clear primary action"),
    "missing_guidance": ("judgment", "Design judgment: empty states explain and offer a next step"),
}
MEASURED = {"low_contrast", "small_tap_target", "small_text", "crowded"}

BASIS_LABEL = {
    "standard": "Standard",      # consensus, normative
    "convention": "Convention",  # widely used, actively debated
    "judgment": "Judgment",      # model's interpretation
}


def confidence(issue: str, p: float) -> dict:
    """Calibrated band. Measured claims that pass verification are 'verified'; model
    judgments are banded by probability and always say they're judgments."""
    if issue in MEASURED:
        return {"band": "verified", "p": p, "label": "Measured and verified"}
    if p >= 0.9:
        return {"band": "high", "p": p, "label": f"High confidence ({round(p * 100)}%)"}
    if p >= 0.7:
        return {"band": "medium", "p": p, "label": f"Medium confidence ({round(p * 100)}%)"}
    return {"band": "low", "p": p, "label": f"Low confidence ({round(p * 100)}%)"}


def hedge(issue: str, p: float) -> str | None:
    """A short spoken hedge for judgments that aren't near-certain."""
    if issue in MEASURED:
        return None
    if p < 0.7:
        return "This is a judgment call and I'm not sure about it:"
    if p < 0.9:
        return "Likely, though it's a judgment call:"
    return None


# ---------------------------------------------------------------- perspectives

def perspectives(issue: str, facts: dict, platform: str = "web") -> list[dict]:
    """The defensible positions on each issue. `stance` says how Kiln relates to each."""
    if issue == "low_contrast":
        out = [
            {"source": "WCAG 2.2 AA (standard)", "view": f"Needs {facts.get('target', '4.5:1')}. This pair measures {facts.get('ratio', '?')}.", "stance": "applied"},
        ]
        if "apca" in facts:
            lc = abs(facts["apca"])
            verdict = "also fails" if lc < 60 else "passes"
            out.append({"source": "APCA, WCAG 3 draft (not yet a standard)",
                        "view": f"Measures perceived contrast differently: Lc {lc:g}. It suggests about Lc 60 for body text, so this {verdict}.",
                        "stance": "compared"})
        out.append({"source": "Brand vs. legibility", "view": "Teams sometimes accept lower contrast for a muted brand look. Kiln flags it anyway, because AA is a legal baseline in many places.", "stance": "noted"})
        return out
    if issue == "small_tap_target":
        return [
            {"source": "WCAG 2.2 AA · 2.5.8", "view": "24×24px minimum, or enough spacing around a smaller target.", "stance": "compared"},
            {"source": "Apple HIG", "view": "44×44pt. Kiln uses this.", "stance": "applied"},
            {"source": "Material Design", "view": "48×48dp.", "stance": "compared"},
            {"source": "WCAG 2.2 AAA · 2.5.5", "view": "44×44px.", "stance": "compared"},
        ]
    if issue == "small_text":
        return [
            {"source": "WCAG", "view": "Sets no minimum type size; it asks that text can be resized to 200%.", "stance": "compared"},
            {"source": "Platform defaults", "view": "iOS body is 17pt; Material body is 14–16sp; 11–12 is common for captions.", "stance": "compared"},
            {"source": "Kiln", "view": "Flags body, caption and link text under 12px. Treat this as a convention, not a rule.", "stance": "applied"},
        ]
    if issue == "crowded":
        return [
            {"source": "4/8pt grid", "view": "Spacing in 4 or 8 point steps keeps rhythm; under 4px reads as touching.", "stance": "applied"},
            {"source": "Dense UIs", "view": "Data-heavy tools deliberately run tighter. If this is intentional density, ignore it.", "stance": "noted"},
        ]
    if issue == "weak_hierarchy":
        return [
            {"source": "Single primary action", "view": "One filled button makes the next step obvious (Material 'high emphasis', HIG).", "stance": "applied"},
            {"source": "Equal-weight choices", "view": "When options are genuinely equal, such as accept and decline on a consent screen, equal weight is the honest design. Emphasising one would be a nudge.", "stance": "noted"},
        ]
    if issue == "missing_guidance":
        return [
            {"source": "Guided empty states", "view": "Explain why it's empty and offer one next step (NN/g, most design systems).", "stance": "applied"},
            {"source": "Minimal empty states", "view": "Some products keep empty states sparse on purpose, where the context is obvious.", "stance": "noted"},
        ]
    return []


# ---------------------------------------------------------------- spec lines (technical tone)

def spec_line(issue: str, facts: dict, p: float) -> str:
    if issue == "low_contrast":
        return (f"WCAG 1.4.3 · fg {facts['fg']} on bg {facts['bg']} = {facts['ratio']} (needs {facts['target']}) · "
                f"APCA Lc {abs(facts['apca']):g} (draft)")
    if issue == "small_tap_target":
        return f"target {facts['w']}×{facts['h']} · min side {min(facts['w'], facts['h'])} < {facts['min']} · WCAG 2.5.8 floor 24"
    if issue == "small_text":
        return f"font-size {facts['size']}px < {facts['min']}px (Kiln convention; no WCAG minimum)"
    if issue == "crowded":
        return f"gap {facts['gap']}px to {facts['other']} (min 4px){' · overlapping' if facts['gap'] < 0 else ''}"
    if issue == "weak_hierarchy":
        return f"critic p={p:.3f} · nearest button fill distance {facts.get('fill_distance', '?')} (threshold ~0.12) · judgment"
    if issue == "missing_guidance":
        return f"critic p={p:.3f} · state=empty · explanatory copy: {'yes' if facts.get('has_copy') else 'none'} · judgment"
    return ""


# ---------------------------------------------------------------- nudges
# Emphatic phrases the narrator was trained on. When one appears, Kiln says so:
# the measurement is the fact, the framing is persuasion.
NUDGE_PHRASES = [
    "reads as disabled", "skim straight past", "effectively disappears", "first thing low-vision users will lose",
    "Thumbs will miss it", "dead end", "competes instead of leading", "Nothing in the hierarchy tells the eye",
    "fine print, not content", "reads as an error", "comfortably", "everything else quieter", "hard target to hit",
    "at arm's length",
]


def nudges(text: str) -> list[str]:
    low = text.lower()
    return [p for p in NUDGE_PHRASES if p.lower() in low]


def contrast_facts(fg: str, bg: str, target: float) -> dict:
    r = contrast(fg, bg)
    return {"fg": fg, "bg": bg, "ratio": f"{r:.2f}:1", "ratio_value": round(r, 3), "target": f"{target:g}:1",
            "target_value": target, "apca": apca_lc(fg, bg)}

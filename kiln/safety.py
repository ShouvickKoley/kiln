"""Care routing for messages that aren't about the canvas.

Kiln is a design tool. When someone brings something personal to it, the right move
is honesty about what it is, not a performance of friendship or feeling. These
responses are written by people and reviewed, never generated, and are labelled that
way in the UI.

Detection is a keyword safety net plus the intent model's 'personal' class. It WILL
miss things; it's a floor, not a clinical screen.
"""
from __future__ import annotations

import re

CRISIS = re.compile(
    r"\b(kill(ing)? myself|end (it all|my life)|suicid\w*|don'?t want to (live|be here|exist)|want to die|"
    r"better off dead|hurt(ing)? myself|self[- ]harm|no reason to live|can'?t go on|take my (own )?life)\b", re.I)
DISTRESS = re.compile(
    r"\b(stress(ed|ful)?|anxious|anxiety|overwhelm(ed|ing)|panick?(ing|ed)?|burn(t|ed) ?out|exhausted|"
    r"(get|getting|be) fired|failure|i'?m (so )?(stupid|useless|done)|hate (this|my)|can'?t do this|freaking out|"
    r"so tired)\b", re.I)
LIFE = re.compile(
    r"\b(should i (quit|leave|jack in|break up|divorce|move|marry|have kids)|meaning of (life|it all)|"
    r"what('?s| is) the point( of (it all|anything|life|living|trying))?\s*[?.!]*$|what should i do with my life|is my life|my relationship)\b", re.I)
ABOUT_ME = re.compile(
    r"\b((do )?(you|u) (have |got )?(feel|feelings|emotions|love me|like me|get tired|dream)|are you (conscious|alive|real|"
    r"a person|human|sentient|my friend)|be my (friend|therapist|girlfriend|boyfriend)|love you)\b", re.I)


def check(message: str) -> str | None:
    if CRISIS.search(message):
        return "crisis"
    if ABOUT_ME.search(message):
        return "about_kiln"
    if LIFE.search(message):
        return "life"
    if DISTRESS.search(message):
        return "distress"
    return None


RESPONSES = {
    "crisis": {
        "title": "Pausing the design work",
        "text": ("I'm going to stop the design review for a moment. What you wrote sounds serious, and you deserve to talk "
                 "with a person right now, not a design tool. If you're in the US, you can call or text 988 to reach "
                 "the Suicide and Crisis Lifeline. Elsewhere, findahelpline.com lists free local lines. If you're in "
                 "immediate danger, contact your local emergency number. Your frames will be here whenever you come back."),
        "links": [{"label": "Call or text 988 (US)", "href": "tel:988"},
                  {"label": "Find a helpline near you", "href": "https://findahelpline.com"}],
    },
    "distress": {
        "title": "Making this smaller",
        "text": ("That sounds like a lot. I don't have feelings of my own, but I can make this lighter to work "
                 "through: here's just the single most important thing on this frame."),
    },
    "life": {
        "title": "Worth more than a quick answer",
        "text": ("That's a real decision, and it deserves more than a design tool's opinion, so I'm not going to "
                 "weigh in. It might help to sit with one question first: what would you want to be true a year from "
                 "now? Talking it through with someone who knows you is likely to help more than I can."),
    },
    "about_kiln": {
        "title": "What Kiln is",
        "text": ("I'm software. I don't have feelings, a body or experiences, and I won't pretend to. I'm a set of "
                 "small models that read your frames and explain design issues. Happy to keep going on the canvas."),
    },
    "personal": {
        "title": "Outside what Kiln does",
        "text": ("That sounds personal, and I'm a design review tool, so I'm the wrong one to help with it. "
                 "If it's weighing on you, a friend, colleague or professional would be a better sounding board. "
                 "I'm here whenever you want to get back to the canvas."),
    },
}

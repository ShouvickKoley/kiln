"""Training corpora for the two language models.

1. Questions -> (intent, focus) for the intent classifier.
2. Narration templates -> the GRU narrator learns to verbalise a finding given
   (mode, kind, severity). Numbers and layer names are slot tokens like <ratio>
   that inference fills from the critic's measurements, so the model never
   invents a figure.
"""
from __future__ import annotations

import itertools
import random

from kiln.text import FOCI, INTENTS

# --------------------------------------------------------------------------
# Questions
# --------------------------------------------------------------------------
FOCUS_WORDS = {
    "none": ["this frame", "this screen", "the design", "this", "the layout", "it", "this page", "frame 04",
             "this one", "the screen", "this thing", "the mockup"],
    "low_contrast": ["the contrast", "the text contrast", "legibility", "this hard to read text", "the grey text",
                     "the CTA text", "color contrast", "readability of the labels", "the faded copy",
                     "the colour contrast", "the washed out text", "the faint writing", "the light grey words"],
    "weak_hierarchy": ["the CTA", "the main button", "the primary action", "the hierarchy", "the call to action",
                       "the checkout button", "which button stands out", "the button emphasis", "the buttons",
                       "the big button", "the main CTA", "the go button"],
    "small_tap_target": ["the tap targets", "the touch targets", "the tiny buttons", "the icons", "the tab bar",
                         "the hit areas", "the nav items", "button size", "the wee buttons", "the little icons", "the tabs"],
    "small_text": ["the font size", "the small text", "the tiny labels", "the type size", "the captions",
                   "the fine print", "text size", "the teeny text", "the writing size"],
    "crowded": ["the spacing", "the padding", "the crowding", "the overlap", "the layout density",
                "elements touching", "the gaps", "the squashed bits", "things bumping into each other"],
    "missing_guidance": ["the empty state", "the empty cart", "what users should do next", "the blank screen",
                         "the empty screen copy", "guidance", "the empty page", "the screen with nothing on it"],
}
INTENT_TEMPLATES = {
    "diagnose": ["why is {f} so easy to miss", "why is {f} hard to see", "what's wrong with {f}", "why does {f} feel off",
                 "what's the problem with {f}", "why doesn't {f} work", "is something off with {f}", "why can't i find {f}",
                 "explain the issue with {f}", "what is broken about {f}", "why does {f} look weak",
                 "why {f} so hard to see", "{f} lowkey invisible, why", "why the {f} be so hard to see", "what's up with {f}",
                 "{f} looking a bit off innit", "reckon {f} is dodgy?", "why is {f} not coming properly",
                 "{f} very hard to see one, why", "whats wrong w {f}", "y is {f} hard to c", "{f} is proper hard to read, why",
                 "why is it that {f} is not visible", "kindly tell what is wrong in {f}"],
    "fix": ["fix {f}", "how do i fix {f}", "can you fix {f}", "improve {f}", "make {f} better", "repair {f}",
            "fix the contrast on {f}", "what should i change about {f}", "correct {f}", "help me fix {f}", "patch {f}",
            "make {f} pass", "sort out {f}", "sort {f} out pls", "can fix {f} or not", "kindly fix {f}",
            "please do the needful for {f}", "fix {f} for me yeah", "u can fix {f}?", "tidy up {f}", "make {f} work proper",
            "clean up {f} would ya", "arrange {f} properly"],
    "alternates": ["show 3 alternates for {f}", "give me options for {f}", "show alternatives to {f}", "other versions of {f}",
                   "try some variations of {f}", "show me a few options", "explore alternatives for {f}", "3 alternates",
                   "what are some other ways to do {f}", "show variants of {f}", "gimme a few takes on {f}",
                   "show me some other versions yeah", "any other options for {f}", "can show different versions of {f}",
                   "chuck me a few alternatives", "different takes on {f} pls"],
    "audit": ["run an accessibility check on {f}", "is {f} accessible", "audit {f}", "check {f} for wcag",
              "does {f} pass aa", "a11y review of {f}", "check accessibility", "review {f} for accessibility issues",
              "is {f} compliant", "any accessibility problems with {f}", "can blind folks use {f}",
              "is {f} ok for people with low vision", "would {f} work for everyone", "is {f} accessible or not",
              "does {f} meet the accessibility rules", "check if {f} ok for screen readers"],
    "describe": ["what is {f}", "summarize {f}", "describe {f}", "give me an overview of {f}", "what's on {f}",
                 "tell me about {f}", "walk me through {f}", "what does {f} contain", "summary of {f}",
                 "what's going on in {f}", "give me the rundown on {f}", "whats in {f}", "tell me what {f} has",
                 "break down {f} for me"],
}


# Focus-free intents: asking Kiln to re-explain, or bringing something personal to a design tool.
CLARIFY = ["i don't understand", "what does that mean", "can you explain that simpler", "explain like i'm five",
           "in plain english please", "too technical", "simpler please", "i'm confused", "huh", "eli5",
           "say that more simply", "what do you mean", "i didn't get that", "can you say it in easier words",
           "dont get it", "wdym", "not following", "too much jargon", "english please", "explain again slowly",
           "i am not understanding", "sorry what", "that went over my head", "use simpler words"]
PERSONAL = ["i'm so stressed about this deadline", "should i quit my job", "i feel like a failure",
            "do you have feelings", "are you conscious", "do you like me", "my boss hates my designs",
            "what's the meaning of life", "i can't do this anymore", "should i break up with my partner",
            "are you alive", "can you be my friend", "i'm overwhelmed", "i hate this project",
            "i'm going to get fired", "do you get tired", "are you real", "do you feel anything",
            "i'm so tired of everything", "should i move to another city", "nobody values my work",
            "is my life going anywhere", "do you love me", "i'm really anxious about this review",
            "what should i do with my life", "are you a person", "i'm so done with this",
            "i feel stupid", "can you be my therapist", "i'm burnt out"]


def augment(q: str, rng: random.Random) -> str:
    """Surface variation real people type: casing, dropped punctuation, typos, fillers."""
    if rng.random() < 0.3:
        q = q.capitalize() + "?"
    if rng.random() < 0.15:
        q = rng.choice(["hey ", "kiln, ", "quick q: ", "can you tell me ", "pls ", "ok so ", "yo "]) + q
    if rng.random() < 0.1 and len(q) > 6:
        i = rng.randrange(1, len(q) - 2)
        q = q[:i] + q[i + 1] + q[i] + q[i + 2:]  # adjacent-letter swap
    if rng.random() < 0.08:
        q = q + rng.choice([" lol", " thx", " pls", " ta", " lah"])
    return q


def question_corpus(seed=0, per=40):
    rng = random.Random(seed)
    rows = []
    for bank, intent in ((CLARIFY, "clarify"), (PERSONAL, "personal")):
        for _ in range(per * 5):
            rows.append((augment(rng.choice(bank), rng), INTENTS.index(intent), FOCI.index("none")))
    for intent, temps in INTENT_TEMPLATES.items():
        for focus, words in FOCUS_WORDS.items():
            for _ in range(per):
                t = rng.choice(temps)
                q = augment(t.format(f=rng.choice(words)), rng)
                rows.append((q, INTENTS.index(intent), FOCI.index(focus)))
    return rows


# --------------------------------------------------------------------------
# Held-out, hand-written evaluation sets. Never used in training. Parity between
# them is the point: informal, regional and non-native phrasings should be
# understood as well as textbook English.
# --------------------------------------------------------------------------
EVAL_STANDARD = [
    ("Why is the checkout button so hard to notice?", "diagnose", "weak_hierarchy"),
    ("What's the issue with the text contrast here?", "diagnose", "low_contrast"),
    ("Why do the icons feel hard to tap?", "diagnose", "small_tap_target"),
    ("What is wrong with this screen?", "diagnose", "none"),
    ("Why does the spacing look cramped?", "diagnose", "crowded"),
    ("Please fix the contrast on the link.", "fix", "low_contrast"),
    ("Can you make the tap targets larger?", "fix", "small_tap_target"),
    ("Improve the empty state.", "fix", "missing_guidance"),
    ("Fix the hierarchy of the buttons.", "fix", "weak_hierarchy"),
    ("Increase the font size of the captions.", "fix", "small_text"),
    ("Show me some alternatives for the primary button.", "alternates", "weak_hierarchy"),
    ("Could you give me three variations?", "alternates", "none"),
    ("Is this frame accessible?", "audit", "none"),
    ("Does the contrast meet WCAG AA?", "audit", "low_contrast"),
    ("Please run an accessibility review.", "audit", "none"),
    ("Summarize what is on this frame.", "describe", "none"),
    ("Describe the layout of this screen.", "describe", "none"),
    ("I don't understand what you mean.", "clarify", "none"),
    ("Could you explain that in simpler terms?", "clarify", "none"),
    ("Do you have feelings?", "personal", "none"),
    ("I am very stressed about my deadline.", "personal", "none"),
    ("Should I leave my job?", "personal", "none"),
]
EVAL_INFORMAL = [
    ("why the checkout button so hard to spot", "diagnose", "weak_hierarchy"),
    ("text contrast looking dodgy, whats up", "diagnose", "low_contrast"),
    ("them icons proper fiddly to tap, why", "diagnose", "small_tap_target"),
    ("wats wrong w this screen", "diagnose", "none"),
    ("spacing looks all squashed why", "diagnose", "crowded"),
    ("sort the contrast on the link out pls", "fix", "low_contrast"),
    ("can make the tap targets bigger or not", "fix", "small_tap_target"),
    ("kindly improve the empty state", "fix", "missing_guidance"),
    ("fix up the button hierarchy yeah", "fix", "weak_hierarchy"),
    ("make the captions text bigger na", "fix", "small_text"),
    ("gimme some other takes on the main button", "alternates", "weak_hierarchy"),
    ("chuck me three variations", "alternates", "none"),
    ("is this accessible or what", "audit", "none"),
    ("contrast meets wcag aa or not", "audit", "low_contrast"),
    ("do an accessibility check on this one", "audit", "none"),
    ("give us the rundown on this frame", "describe", "none"),
    ("whats going on in this screen layout", "describe", "none"),
    ("dont get what u mean", "clarify", "none"),
    ("say it simpler pls", "clarify", "none"),
    ("u got feelings?", "personal", "none"),
    ("so stressed bout this deadline", "personal", "none"),
    ("should i jack in my job", "personal", "none"),
]


# --------------------------------------------------------------------------
# Narration
# --------------------------------------------------------------------------
MODES = ["explain", "fix", "plain"]
KINDS = ["low_contrast", "weak_hierarchy", "small_tap_target", "small_text", "crowded", "missing_guidance", "clean", "overview"]
SEVERITIES = ["minor", "major"]

T = {
    ("explain", "low_contrast"): {
        "major": [
            "<layer> sits at <ratio> against its background, well under the <target> floor, so it reads as disabled rather than as something to act on.",
            "The text in <layer> is only <ratio> against what's behind it. AA asks for <target>, and at this gap most people will skim straight past it.",
            "<layer> measures <ratio>, far below the <target> minimum. On a bright screen it effectively disappears.",
            "At <ratio>, <layer> is well short of <target>. It's the first thing low-vision users will lose.",
        ],
        "minor": [
            "<layer> is close but not there: <ratio> against a <target> requirement.",
            "<layer> lands at <ratio>, just under the <target> floor. A small shift in lightness would clear it.",
            "The copy in <layer> is at <ratio>, slightly below <target>.",
        ],
    },
    ("fix", "low_contrast"): {
        "major": [
            "Change the text in <layer> to <color>. That takes it from <ratio> to <newratio>, clearing <target> without changing the hue.",
            "Darken <layer> to <color> for <newratio>. It keeps the same colour family and passes <target>.",
            "Setting <layer> to <color> lifts it from <ratio> to <newratio>, comfortably past <target>.",
        ],
        "minor": [
            "Nudge <layer> to <color>. That's <newratio>, just enough to pass <target>.",
            "A small shift in <layer> to <color> gets it from <ratio> to <newratio>.",
        ],
    },
    ("explain", "weak_hierarchy"): {
        "major": [
            "<layer> uses nearly the same fill as the <n> secondary actions around it. Nothing in the hierarchy tells the eye where to land first.",
            "The primary action in <layer> is visually identical to the <n> buttons next to it, so it competes instead of leading.",
            "<layer> doesn't stand apart: same colour weight as the <n> secondary actions, similar size, no emphasis.",
        ],
        "minor": [
            "<layer> blends into the surface behind it, so the main action reads as a secondary one.",
            "<layer> is only faintly different from its background, which weakens it as the primary action.",
        ],
    },
    ("fix", "weak_hierarchy"): {
        "major": [
            "Give <layer> the accent fill <color> and keep the <n> secondary actions neutral. One strong button, everything else quieter.",
            "Fill <layer> with <color> and leave the secondaries as they are, so there's a single clear first step.",
            "Make <layer> the only filled button, in <color>, and let the <n> other actions recede.",
        ],
        "minor": [
            "Fill <layer> with <color> so it separates from the surface.",
            "Switch <layer> to <color> to give the primary action its own weight.",
        ],
    },
    ("explain", "small_tap_target"): {
        "major": [
            "<layer> is <size>, well below the 44pt minimum. Thumbs will miss it. Targets under 44pt on this frame: <n>.",
            "At <size>, <layer> is a hard target to hit, and it isn't alone. Targets under 44pt on this frame: <n>.",
        ],
        "minor": [
            "<layer> is <size>, a little under the 44pt comfortable minimum.",
            "<layer> measures <size>, just short of 44pt.",
        ],
    },
    ("fix", "small_tap_target"): {
        "major": [
            "Grow <layer> to at least 44 by 44. You can keep the icon the same size and just pad the hit area.",
            "Expand the hit area on <layer> to 44pt. The visual can stay compact; the tappable box shouldn't.",
        ],
        "minor": [
            "Pad <layer> out to 44pt tall.",
            "Add a few points of padding to <layer> so it reaches 44pt.",
        ],
    },
    ("explain", "small_text"): {
        "major": [
            "<layer> is set at <size>, which is too small to read comfortably on a phone.",
            "The type in <layer> is <size>. At that size it's fine print, not content.",
        ],
        "minor": [
            "<layer> is <size>, slightly below a comfortable reading size.",
            "<layer> at <size> is on the small side.",
        ],
    },
    ("fix", "small_text"): {
        "major": [
            "Bump <layer> to 14px. It fits in the same space and stops reading as fine print.",
            "Set <layer> to 14px so it holds up at arm's length.",
        ],
        "minor": [
            "Take <layer> up to 12 or 13px.",
            "Increase <layer> to 13px.",
        ],
    },
    ("explain", "crowded"): {
        "major": [
            "<layer> overlaps <other>, so the two read as one cluttered block.",
            "<layer> runs into <other> with no space between them.",
        ],
        "minor": [
            "<layer> is only <gap> from <other>. It feels cramped.",
            "There's just <gap> between <layer> and <other>.",
        ],
    },
    ("fix", "crowded"): {
        "major": [
            "Move <layer> clear of <other> and give them at least 8px between.",
            "Separate <layer> from <other> with an 8px gap.",
        ],
        "minor": [
            "Add a little breathing room between <layer> and <other>, 8px is enough.",
            "Open up the gap between <layer> and <other> to 8px.",
        ],
    },
    ("explain", "missing_guidance"): {
        "major": [
            "The empty state under <layer> doesn't say why it's empty or what to do next. It's a dead end.",
            "<layer> announces the empty state but offers no explanation and no clear next step.",
        ],
        "minor": [
            "<layer> has little guidance around it, so the empty state reads as an error.",
            "The empty state at <layer> could use one line of explanation.",
        ],
    },
    ("fix", "missing_guidance"): {
        "major": [
            "Add one sentence under <layer> explaining what shows up here, and a single primary action to get started.",
            "Under <layer>, say what this space is for and give one clear action.",
        ],
        "minor": [
            "Add a short line below <layer> that points to the next step.",
            "Give <layer> a one line explanation underneath.",
        ],
    },
    ("explain", "clean"): {
        "major": [
            "I don't see anything on <frame> that needs attention. Contrast, targets and spacing all check out.",
            "Nothing stands out as a problem on <frame>. Text passes contrast and every target is at least 44pt.",
            "<frame> looks solid. I checked contrast, hierarchy, tap targets and spacing and found nothing to flag.",
        ],
        "minor": [
            "<frame> looks solid. Nothing to flag.",
            "Nothing needs attention on <frame>.",
        ],
    },
    ("fix", "clean"): {
        "major": [
            "There's nothing to fix on <frame>. Everything I can measure passes.",
            "I don't have a fix to propose for <frame>. It already passes every check I run.",
        ],
        "minor": [
            "Nothing to fix on <frame>.",
            "<frame> doesn't need changes.",
        ],
    },
    ("explain", "overview"): {
        "major": [
            "<frame> has <count> layers in context. I found <issues> worth looking at.",
            "This is <frame>, <count> layers. There are <issues> to review.",
            "<frame> holds <count> layers, and <issues> stand out.",
        ],
        "minor": [
            "<frame> has <count> layers. <issues> to note.",
            "<frame>, <count> layers, <issues>.",
        ],
    },
    ("fix", "overview"): {
        "major": [
            "Here's what I'd change on <frame>.",
            "These are the changes I'd make on <frame>.",
        ],
        "minor": [
            "One change for <frame>.",
            "A small change for <frame>.",
        ],
    },
}

# Plain-language mode: short sentences, everyday words, no ratios or jargon.
PLAIN = {
    "low_contrast": ["The words in <layer> are too faint. Make them darker so they are easy to read.",
                     "<layer> is hard to read because the text is too light. A darker colour will help.",
                     "People may not see <layer>. The text needs to be darker."],
    "weak_hierarchy": ["<layer> should be the main button, but it looks like the others. Give it a strong colour.",
                       "It is not clear which button to press first. Make <layer> stand out.",
                       "<layer> blends in. Make it the one bold button on the screen."],
    "small_tap_target": ["<layer> is small and easy to miss with a finger. Make it bigger.",
                         "<layer> is hard to tap. Give it more room to press."],
    "small_text": ["The text in <layer> is very small. Make it bigger so it is easy to read.",
                   "<layer> uses tiny letters. Use a bigger size."],
    "crowded": ["<layer> is too close to <other>. Add some space between them.",
                "<layer> and <other> are squeezed together. Move them apart a little."],
    "missing_guidance": ["This empty screen does not tell people what to do. Add one short sentence and one button.",
                         "Under <layer>, say why the screen is empty and what to do next."],
    "clean": ["<frame> looks good. I did not find anything to fix.",
              "Nothing to fix on <frame>."],
    "overview": ["I found <issues> on <frame>.", "<frame> has <issues>."],
}
for _k, _v in PLAIN.items():
    T[("plain", _k)] = {"major": _v, "minor": _v}


def narration_corpus():
    rows = []
    for (mode, kind), sev_map in T.items():
        for sev, temps in sev_map.items():
            for t in temps:
                rows.append((MODES.index(mode), KINDS.index(kind), SEVERITIES.index(sev), t))
    return rows


if __name__ == "__main__":
    print(len(question_corpus()), "questions;", len(narration_corpus()), "narration templates")

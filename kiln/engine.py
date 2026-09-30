"""Inference engine: onnxruntime + numpy only (this is what runs on Vercel).

analyze(frame)            -> findings the critic model is confident about, with citations
chat(frame, message, ...) -> generator of stream events (status / meta / token / proposal / done)
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort

from . import constraints as C
from . import safety, trust
from .color import contrast, distance
from .privacy import mask, mask_frame
from .voice import speakable
from .features import (
    BUTTONS, INTERACTIVE, ISSUE_LABELS, ISSUES, _gap, _is_leaf, _nested, background_of, featurize, text_contrast,
)
from .proposals import alternates, fix_low_contrast, fix_weak_hierarchy, patch_for
from .text import BOS, EOS, PAD, hash_features, join_token

MODELS = Path(__file__).resolve().parents[1] / "models"
THRESH = 0.5

CHIP_FOR = {
    "low_contrast": "Fix the contrast",
    "weak_hierarchy": "Strengthen the CTA",
    "small_tap_target": "Enlarge tap targets",
    "small_text": "Bump the text size",
    "crowded": "Fix the spacing",
    "missing_guidance": "Add empty-state guidance",
}
A11Y = {"low_contrast", "small_tap_target", "small_text"}


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


class Engine:
    def __init__(self, models_dir: Path = MODELS):
        so = ort.SessionOptions()
        so.intra_op_num_threads = 1
        so.log_severity_level = 3
        load = lambda n: ort.InferenceSession(str(models_dir / n), so, providers=["CPUExecutionProvider"])  # noqa: E731
        self.critic = load("critic.onnx")
        self.intent = load("intent.onnx")
        self.n_init = load("narrator_init.onnx")
        self.n_step = load("narrator_step.onnx")
        self.meta = json.loads((models_dir / "meta.json").read_text())
        self.metrics = json.loads((models_dir / "metrics.json").read_text())
        self.vocab = self.meta["vocab"]
        self.stoi = {t: i for i, t in enumerate(self.vocab)}
        self.slot_ids = {t: i for t, i in self.stoi.items() if t.startswith("<") and t not in (PAD, BOS, EOS)}

    # ------------------------------------------------------------------ critic
    def analyze(self, frame, dismissed=None):
        """dismissed: [{issue, layer}] the person marked 'not an issue'. Their call wins."""
        dismissed = {(d.get("issue"), d.get("layer")) for d in (dismissed or [])}
        t0 = time.perf_counter()
        X, M, kept, dropped = featurize(frame)
        ll, fl = self.critic.run(None, {"x": X[None], "mask": M[None]})
        lp, fp = _sigmoid(ll[0]), _sigmoid(fl[0])
        layers = frame["layers"]
        findings, rejected, considered = [], [], []
        for k, issue in enumerate(ISSUES):
            if 0.15 <= fp[k] < THRESH:
                considered.append({"issue": issue, "label": ISSUE_LABELS[issue], "prob": round(float(fp[k]), 3)})
            if fp[k] < THRESH:
                continue
            cited = [(float(lp[s, k]), kept[s]) for s in range(len(kept)) if lp[s, k] >= THRESH]
            if not cited:
                cited = [(float(lp[: len(kept), k].max()), kept[int(lp[: len(kept), k].argmax())])]
            cited.sort(key=lambda t: -t[0])
            # the model proposes, measurement confirms: measurable issues are only
            # cited on layers where the geometry agrees
            checked = [(p, i) for p, i in cited if self._verify(frame, issue, i, kept)]
            if len(checked) < len(cited):
                rejected.append({"issue": issue, "layers": [layers[i]["name"] for p, i in cited if (p, i) not in checked]})
            cited = [(p, i) for p, i in checked if (issue, layers[i]["id"]) not in dismissed]
            if not cited:
                continue
            f = {
                "issue": issue,
                "label": ISSUE_LABELS[issue],
                "prob": round(float(fp[k]), 3),
                "layers": [{"id": layers[i]["id"], "name": layers[i]["name"], "prob": round(p, 3)} for p, i in cited],
            }
            f["slots"], f["severity"], f["facts"] = self._measure(frame, issue, [i for _, i in cited], kept)
            f["confidence"] = trust.confidence(issue, f["prob"])
            basis, rule = trust.BASIS[issue]
            f["basis"], f["rule"] = basis, rule
            f["evidence"] = "measured" if issue in trust.MEASURED else "model"
            findings.append(f)
        # most confident & most severe first
        findings.sort(key=lambda f: (f["severity"] != "major", -f["prob"]))
        return {
            "findings": findings,
            "context": {
                "kept": [layers[i]["id"] for i in kept],
                "dropped": [{"id": layers[i]["id"], "name": layers[i]["name"]} for i in dropped],
                "total": len(layers),
            },
            "chips": self.chips(findings),
            "unverified": rejected,
            "considered": considered,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        }

    @staticmethod
    def _verify(frame, issue, i, kept):
        L = frame["layers"]
        l = L[i]
        if issue == "low_contrast":
            if not l.get("text"):
                return False
            ratio, large = text_contrast(frame, i)
            return ratio < (3.0 if large else 4.5)
        if issue == "small_tap_target":
            return l["role"] in INTERACTIVE and min(l["w"], l["h"]) < (24 if l["role"] == "link" else 44)
        if issue == "small_text":
            return bool(l.get("text")) and l["role"] in ("body", "caption", "link", "nav_item") and l.get("size", 14) < 12
        if issue == "crowded":
            return _is_leaf(l) and any(j != i and _is_leaf(L[j]) and not _nested(l, L[j]) and _gap(l, L[j]) < 4 for j in kept)
        return True  # hierarchy and guidance are judgement calls: the model's call stands

    @staticmethod
    def chips(findings):
        chips = [CHIP_FOR[f["issue"]] for f in findings[:2]]
        if findings:
            chips.append("Show 3 alternates")
        return chips

    def _measure(self, frame, issue, idxs, kept):
        """Deterministic measurements that fill the narrator's slots. The model decides
        *that* something is wrong and *where*; the numbers always come from geometry."""
        L = frame["layers"]
        i = idxs[0]
        l = L[i]
        q = lambda n: f'"{n}"'  # noqa: E731
        s = {"layer": q(l["name"]), "frame": frame["name"].split("·")[-1].strip()}
        sev = "minor"
        facts = {"layer": l["id"], "layer_name": l["name"]}
        if issue == "low_contrast":
            if l.get("text"):
                ratio, large = text_contrast(frame, i)
                target = 3.0 if large else 4.5
                _, extra = fix_low_contrast(frame, l["id"])
                s.update(ratio=f"{ratio:.1f}:1", target=f"{target:g}:1", **extra)
                sev = "major" if ratio < target - 1.0 else "minor"
                bg = l["fill"] if (l.get("fill") and l["role"] in BUTTONS | {"input"}) else background_of(frame, i)
                facts.update(trust.contrast_facts(l.get("color", "#000000"), bg, target))
        elif issue == "weak_hierarchy":
            others = [j for j in kept if j != i and L[j]["role"] in BUTTONS]
            s["n"] = str(len(others)) if others else "other"
            _, extra = fix_weak_hierarchy(frame, l["id"])
            s.update(extra)
            sev = "major" if others else "minor"
            fills = [L[j]["fill"] for j in others if L[j].get("fill")]
            facts.update(n=len(others), fill_distance=round(min([distance(l.get("fill", "#FFFFFF"), c) for c in fills], default=1.0), 3))
        elif issue == "small_tap_target":
            s["size"] = f'{l["w"]}×{l["h"]}'
            s["n"] = str(sum(1 for j in kept if L[j]["role"] in INTERACTIVE and min(L[j]["w"], L[j]["h"]) < (24 if L[j]["role"] == "link" else 44)))
            sev = "major" if min(l["w"], l["h"]) < 38 else "minor"
            facts.update(w=l["w"], h=l["h"], min=24 if l["role"] == "link" else 44)
        elif issue == "small_text":
            s["size"] = f'{l.get("size", 14)}px'
            s["n"] = str(len(idxs))
            sev = "major" if l.get("size", 14) <= 10 else "minor"
            facts.update(size=l.get("size", 14), min=12)
        elif issue == "crowded":
            cands = [(_gap(l, L[j]), j) for j in kept if j != i and _is_leaf(L[j]) and not _nested(l, L[j])]
            g, j = min(cands, default=(99, i))
            s.update(other=q(L[j]["name"]), gap=f"{max(g, 0):.0f}px", _other_id=L[j]["id"])
            sev = "major" if g < 0 else "minor"
            facts.update(gap=round(float(g), 1), other=L[j]["name"], other_id=L[j]["id"])
        elif issue == "missing_guidance":
            long_body = any(L[j]["role"] in ("body", "caption") and len(L[j].get("text", "")) > 24 for j in kept)
            sev = "minor" if long_body else "major"
            facts.update(has_copy=long_body)
        return s, sev, facts

    # ------------------------------------------------------------------ intent
    def classify(self, message):
        a, b = self.intent.run(None, {"x": hash_features(message)[None]})
        pa, pb = np.exp(a[0] - a[0].max()), np.exp(b[0] - b[0].max())
        pa, pb = pa / pa.sum(), pb / pb.sum()
        return (self.meta["intents"][int(pa.argmax())], float(pa.max()),
                self.meta["foci"][int(pb.argmax())], float(pb.max()))

    # ------------------------------------------------------------------ narrator
    def narrate(self, mode, kind, severity, slots, rng, temperature=0.7, max_len=64):
        """Yields text pieces, one per sampled token. Slots the finding can't fill are
        masked out of the distribution (constrained decoding), so no invented numbers."""
        m = self.meta
        cond = np.zeros((1, len(m["modes"]) + len(m["kinds"]) + len(m["severities"])), dtype=np.float32)
        cond[0, m["modes"].index(mode)] = 1
        cond[0, len(m["modes"]) + m["kinds"].index(kind)] = 1
        cond[0, len(m["modes"]) + len(m["kinds"]) + m["severities"].index(severity)] = 1
        (h,) = self.n_init.run(None, {"cond": cond})
        tok, prev = self.stoi[BOS], None
        banned = np.array([i for t, i in self.slot_ids.items() if t[1:-1] not in slots] + [self.stoi[PAD], self.stoi[BOS]])
        for _ in range(max_len):
            logits, h = self.n_step.run(None, {"tok": np.array([tok], dtype=np.int64), "h": h, "cond": cond})
            lg = logits[0].astype(np.float64)
            if len(banned):
                lg[banned] = -1e9
            if temperature <= 0:
                tok = int(lg.argmax())
            else:
                lg = lg / temperature
                top = np.argsort(lg)[-5:]
                p = np.exp(lg[top] - lg[top].max())
                tok = int(rng.choice(top, p=p / p.sum()))
            word = self.vocab[tok]
            if word == EOS:
                return
            text = slots[word[1:-1]] if word in self.slot_ids else word
            piece = join_token(prev, text)
            prev = word
            yield piece

    # ------------------------------------------------------------------ chat
    ICONS = {"low_contrast": "contrast", "weak_hierarchy": "hierarchy", "small_tap_target": "target",
             "small_text": "type", "crowded": "spacing", "missing_guidance": "empty", "lead": "lead",
             "safety": "care", "rule": "rule"}
    UNIT = {"web": "px", "ios": "pt", "android": "dp"}

    def _localize(self, text, platform, spelling):
        text = re.sub(r"(\d+)pt\b", lambda m: m.group(1) + self.UNIT.get(platform, "px"), text)
        if spelling == "en-GB":
            return re.sub(r"\bcolor", "colour", text)
        return re.sub(r"\bcolour", "color", text).replace("Colour", "Color")

    @staticmethod
    def _merge_ops(ops):
        out, by_layer = [], {}
        for op in ops:
            if op["op"] == "set" and op["layer"] in by_layer:
                by_layer[op["layer"]]["props"].update(op["props"])
            elif op["op"] == "set":
                o = {"op": "set", "layer": op["layer"], "props": dict(op["props"])}
                by_layer[op["layer"]] = o
                out.append(o)
            else:
                out.append(op)
        return out

    def _patch_lines(self, frame, ops):
        byid = {l["id"]: l for l in frame["layers"]}
        lines = []
        for k, op in enumerate(ops):
            if op["op"] == "set":
                l = byid.get(op["layer"], {})
                geo = [p for p in ("x", "y", "w", "h") if p in op["props"]]
                if geo:  # position + size read as one change: the layer's box
                    new = {**{p: l.get(p) for p in ("x", "y", "w", "h")}, **{p: op["props"][p] for p in geo}}
                    lines.append({"op": k, "props": geo, "layer": l.get("name", op["layer"]), "prop": "box",
                                  "from": f'{l.get("w")}×{l.get("h")} at {l.get("x")},{l.get("y")}',
                                  "to": f'{new["w"]}×{new["h"]} at {new["x"]},{new["y"]}'})
                for prop, to in op["props"].items():
                    if prop not in geo:
                        lines.append({"op": k, "props": [prop], "layer": l.get("name", op["layer"]), "prop": prop, "from": l.get(prop), "to": to})
            elif op["op"] == "insert":
                lines.append({"op": k, "layer": op["layer"]["name"], "prop": "insert", "from": None, "to": op["layer"].get("text", "")})
            elif op["op"] == "shift":
                lines.append({"op": k, "layer": "layers below", "prop": "move", "from": None, "to": f"down {op['dy']}"})
        return lines

    def chat(self, frame, message, seed=0, pace_ms=0, tone="balanced", constraints=None, dismissed=None,
             platform="web", spelling="en-US", only_issue=None):
        """Streams one reply as events. Every block of text arrives with its evidence:
        basis (standard / convention / judgment), confidence band, cited layers, the
        measurements behind it, and the other reasonable views on it."""
        rng = np.random.default_rng(seed)
        temperature = 0.35 if seed == 0 else 0.9
        loc = lambda t: self._localize(t, platform, spelling)  # noqa: E731

        # 1 · privacy: mask identifiers before anything else touches them
        message_masked, mcounts = mask(message)
        frame, fcounts = mask_frame(frame)
        if mcounts or fcounts:
            yield {"type": "privacy", "message": mcounts, "frame": fcounts}

        # 2 · rules the person set
        new, clear = C.parse(message)
        active = [{**c, "label": loc(c["label"])} for c in C.merge(constraints or [], new, clear)]
        yield {"type": "constraints", "active": active, "added": [c["id"] for c in new], "cleared": clear}
        rule = {c["id"]: c["value"] for c in active}
        if rule.get("plain"):
            tone = "plain"

        # 3 · care routing happens before any design work
        level = safety.check(message)
        if level == "crisis":
            yield from self._care_reply("crisis")
            return

        yield {"type": "status", "text": f"Reading frame {frame['name'].split('·')[0].strip()}"}
        analysis = self.analyze(frame, dismissed)
        yield {"type": "status", "text": "Checking contrast, hierarchy, targets and spacing"}
        intent, ip, focus, fp = self.classify(message_masked)
        findings = analysis["findings"]
        yield {"type": "meta", "intent": intent, "intent_p": round(ip, 3), "focus": focus, "focus_p": round(fp, 3),
               "findings": findings, "context": analysis["context"], "latency_ms": analysis["latency_ms"], "tone": tone}

        if level in ("life", "about_kiln") or (intent == "personal" and level is None and ip > 0.6):
            yield from self._care_reply(level or "personal", chips=self.chips(findings))
            return
        care_prefix = None
        if level == "distress":
            care_prefix = safety.RESPONSES["distress"]
            tone, intent = "concise", "diagnose"
            rule["top"] = 1  # one thing, whatever else was asked
        if intent == "clarify":
            tone, intent = "plain", "describe"
        if intent == "personal":
            intent = "describe"

        # 4 · plan
        focused = [f for f in findings if f["issue"] == focus] if focus != "none" else []
        mode = "fix" if intent in ("fix", "alternates") else "explain"
        narr_mode = "plain" if tone == "plain" else mode
        if only_issue:
            chosen = [f for f in findings if f["issue"] == only_issue]
        elif intent == "audit":
            chosen = [f for f in findings if f["issue"] in A11Y] or focused
        elif focused:
            chosen = focused
        elif intent == "diagnose":
            chosen = findings[:2]
        else:
            chosen = findings[:3]
        name = frame["name"].split("·")[-1].strip()
        blocks = []
        if care_prefix:
            blocks.append({"kind": "safety", "rule_text": care_prefix["text"], "title": care_prefix["title"]})
        if rule.get("only"):
            chosen = [f for f in findings if f["issue"] == rule["only"]]
        if not chosen and focus != "none" and findings and not rule.get("only") and not only_issue:
            blocks.append({"kind": "rule", "rule_text": f"I don't see a {ISSUE_LABELS[focus].lower()} problem on {name}. Here's what does stand out.",
                           "title": "Nothing on that"})
            chosen = findings[:2]
        if tone == "concise":
            chosen = chosen[:2]
        if rule.get("top"):
            chosen = chosen[: rule["top"]]
        if mode == "fix":
            # one fix per layer: strengthening a CTA already sets a passing text colour
            wh = {l["id"] for f in chosen if f["issue"] == "weak_hierarchy" for l in f["layers"]}
            chosen = [f for f in chosen if not (f["issue"] == "low_contrast" and {l["id"] for l in f["layers"]} <= wh)]
        if not chosen:
            blocks.append({"kind": "lead", "narr": ("clean", "major", {"frame": name}), "cite": []})
        elif tone != "concise" and not only_issue and (intent in ("describe", "audit") or (mode == "fix" and len(chosen) > 1)):
            n = len(chosen)
            blocks.append({"kind": "lead", "cite": [],
                           "narr": ("overview", "major" if n > 1 else "minor",
                                    {"frame": name, "count": str(len(analysis["context"]["kept"])), "issues": f"{n} issue{'s' if n != 1 else ''}"})})
        for f in chosen:
            blocks.append({"kind": f["issue"], "finding": f, "cite": [l["id"] for l in f["layers"]],
                           "narr": (f["issue"], f["severity"], {k: v for k, v in f["slots"].items() if not k.startswith("_")})})

        # 5 · stream, one evidence-carrying block at a time
        max_words = rule.get("words")
        one_sentence = bool(rule.get("one_sentence")) or tone == "concise"
        words_used, truncated, all_text, streamed = 0, False, [], []
        for bi, b in enumerate(blocks):
            bid = f"b{bi}"
            f = b.get("finding")
            if "rule_text" in b:
                sentences = [b["rule_text"]]
            else:
                sentences = []
                h = trust.hedge(f["issue"], f["prob"]) if f else None
                if h:
                    sentences.append(h)
                m = narr_mode
                if rule.get("no_color") and m == "fix" and f and f["issue"] in ("low_contrast", "weak_hierarchy"):
                    m = "explain"  # don't narrate a colour change the person ruled out
                sentences += list(self._sentences(m, *b["narr"], rng, temperature))
                if one_sentence:
                    sentences = sentences[: (2 if h else 1)]
            sentences = [loc(x) for x in sentences]
            authored = "rule_text" in b  # Kiln's own care/rule notices don't spend the person's word budget
            if max_words and not authored and words_used + len(sentences[0].split()) > max_words:
                truncated = True
                break
            ev = {"type": "block", "id": bid, "kind": b["kind"], "icon": self.ICONS.get(b["kind"], "lead"),
                  "cite": b.get("cite", []), "title": b.get("title") or (f["label"] if f else None)}
            if f:
                ev.update(basis=f["basis"], basis_label=trust.BASIS_LABEL[f["basis"]], rule=f["rule"], evidence=f["evidence"],
                          confidence=f["confidence"], facts=f["facts"], prob=f["prob"], issue=f["issue"],
                          perspectives=trust.perspectives(f["issue"], f["facts"], platform),
                          spec=loc(trust.spec_line(f["issue"], f["facts"], f["prob"])) if tone == "technical" else None,
                          phrasing="narrator")
            elif "rule_text" in b:
                ev.update(basis="authored", basis_label="Written by Kiln's authors", phrasing="authored")
            else:
                ev.update(basis="summary", basis_label="Summary", phrasing="narrator")
            yield ev
            text = ""
            for sent in sentences:
                n = 0 if authored else len(sent.split())
                if max_words and words_used + n > max_words:
                    truncated = True
                    break
                for piece in re.findall(r"\s*\S+", sent):
                    if pace_ms:
                        time.sleep(pace_ms / 1000)
                    yield {"type": "token", "block": bid, "text": piece}
                text += sent if not text else " " + sent.lstrip()
                words_used += n
            all_text.append(text)
            if f and text:
                streamed.append(f)
            yield {"type": "block_end", "id": bid, "text": text, "speech": speakable(text), "words": len(text.split()),
                   "nudges": trust.nudges(text) if f else []}
            if truncated:
                break

        # 6 · proposals: nothing touches the canvas until the person inserts
        order = lambda fs: sorted(fs, key=lambda f: f["issue"] == "weak_hierarchy")  # noqa: E731
        shown = streamed
        colour_blocked = False
        if shown and intent == "alternates" and not rule.get("no_color"):
            opts = alternates(frame, order(shown))
            for o in opts:
                o["ops"] = self._merge_ops(o["ops"])
                o["lines"] = self._patch_lines(frame, o["ops"])
            yield {"type": "alternates", "options": opts,
                   "disclosure": "Ember is listed first because it's this frame's existing accent. That's a default, not a recommendation."}
        elif shown:
            ops = [op for f in order(shown) for op in patch_for(frame, f)]
            if rule.get("no_color"):
                kept_ops = []
                for op in ops:
                    if op["op"] == "set" and ({"color", "fill"} & set(op["props"])):
                        colour_blocked = True
                        rest = {k: v for k, v in op["props"].items() if k not in ("color", "fill")}
                        if rest:
                            kept_ops.append({**op, "props": rest})
                    else:
                        kept_ops.append(op)
                ops = kept_ops
            ops = self._merge_ops(ops)
            if ops:
                lines = self._patch_lines(frame, ops)
                yield {"type": "proposal", "label": "Insert fixes" if len(ops) > 1 else "Insert fix", "ops": ops,
                       "lines": lines, "review": len(lines) > 2}
        if colour_blocked:
            yield {"type": "block", "id": "brule", "kind": "rule", "icon": "rule", "cite": [], "title": "Rule respected",
                   "basis": "authored", "basis_label": "Your rule", "phrasing": "authored"}
            t = "Colour changes are off, so no new colours are proposed."
            yield {"type": "token", "block": "brule", "text": loc(t)}
            yield {"type": "block_end", "id": "brule", "text": loc(t), "speech": speakable(loc(t)), "words": len(t.split()), "nudges": []}

        # 7 · what Kiln looked at but won't claim
        if analysis["considered"] or analysis["unverified"]:
            yield {"type": "considered", "items": analysis["considered"], "unverified": analysis["unverified"]}

        # 8 · did we honour the rules?
        comp = []
        for c in active:
            if c["id"] == "words":
                comp.append({"id": "words", "ok": words_used <= c["value"], "detail": f"{words_used} / {c['value']} words" + (" (stopped early to stay under)" if truncated else "") + (" · Kiln's own notices not counted" if colour_blocked or any("rule_text" in b for b in blocks) else "")})
            elif c["id"] == "one_sentence":
                comp.append({"id": "one_sentence", "ok": True, "detail": "One sentence per point"})
            elif c["id"] == "only":
                comp.append({"id": "only", "ok": all(b.get("finding", {}).get("issue", c["value"]) == c["value"] for b in blocks if b.get("finding")), "detail": c["label"]})
            elif c["id"] == "no_color":
                comp.append({"id": "no_color", "ok": True, "detail": "No colour changes proposed" if colour_blocked or intent != "alternates" else "Alternates skipped"})
            elif c["id"] == "top":
                comp.append({"id": "top", "ok": len(shown) <= c["value"], "detail": f"{len(shown)} of max {c['value']}"})
            elif c["id"] == "plain":
                comp.append({"id": "plain", "ok": True, "detail": "Plain-language wording"})
        if comp:
            yield {"type": "compliance", "items": comp}
        yield {"type": "chips", "chips": self.chips(findings)}
        yield {"type": "done", "speech": speakable(" ".join(all_text)), "words": words_used, "tone": tone}

    def _sentences(self, mode, kind, sev, slots, rng, temperature):
        """Decode a narration and split it into sentences (so word limits cut cleanly)."""
        text = "".join(self.narrate(mode, kind, sev, slots, rng, temperature)).strip()
        for s in re.split(r"(?<=[.!?])\s+", text):
            if s:
                yield s

    def _care_reply(self, level, chips=None):
        r = safety.RESPONSES[level]
        yield {"type": "safety", "level": level, "title": r["title"], "links": r.get("links", [])}
        yield {"type": "block", "id": "care", "kind": "safety", "icon": "care", "cite": [], "title": r["title"],
               "basis": "authored", "basis_label": "Written by Kiln's authors, not generated", "phrasing": "authored"}
        for piece in re.findall(r"\s*\S+", r["text"]):
            yield {"type": "token", "block": "care", "text": piece}
        yield {"type": "block_end", "id": "care", "text": r["text"], "speech": speakable(r["text"]), "words": len(r["text"].split()), "nudges": []}
        if chips is not None:
            yield {"type": "chips", "chips": chips}
        yield {"type": "done", "speech": speakable(r["text"]), "care": level}

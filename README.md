# Kiln — working prototype

A working prototype of **Kiln**, the AI collaborator from the case study *"Designing an AI that stays in the room."* Kiln sits inside a design canvas. It reads the frame you select, finds real problems in it, cites the exact layer behind each one, and streams its answer token by token. Nothing on the canvas changes until you choose **Insert**.

The ML is written in **PyTorch**, exported to **ONNX**, and served by **onnxruntime** from one FastAPI function on **Vercel**.

```
┌─────────────── canvas (source of truth) ───────────────┐    ┌──────────── Kiln panel ────────────┐
│  frames = JSON layer trees                              │    │ queued → thinking → streaming →    │
│  select frame ──────── attaches as context ───────────────►  │ complete | error | stopped          │
│  ◄──────────── Insert applies a patch (undoable) ─────────┤  │ cite chips highlight layers         │
└─────────────────────────────────────────────────────────┘    └────────────────────────────────────┘
                                   │ POST /api/chat (NDJSON stream)
                                   ▼
   featurize (numpy) ─► Critic (set transformer) ─► findings + per-layer citations
   question ─────────► Intent (hashed n-gram MLP) ─► intent + focus
   findings + intent ─► Narrator (conditional GRU) ─► tokens, streamed as they're sampled
                                                     (slots like <ratio> filled from measured geometry)
```

## The three models

| Model | Architecture | What it does |
|---|---|---|
| **Critic** | 3-block set transformer over up to 24 layers (~250k params) | Scores six issues per layer: low contrast, weak hierarchy, small tap target, small text, crowded spacing, missing empty-state guidance. Frame score = masked max over layers (multiple-instance learning), so the layer driving a finding is the one Kiln cites. For measurable issues, a citation is kept only if the layer's measured geometry confirms it. |
| **Intent** | Hashed word/char n-grams → MLP with two heads | Maps a free-text question to *what you want* (diagnose, fix, alternates, audit, describe) and *which issue* it's about. |
| **Narrator** | Word-level conditional GRU | Writes each sentence one token at a time, conditioned on (mode, finding, severity). Numbers and layer names are slot tokens filled from measurements, and slots a finding can't fill are masked out during decoding, so it can't invent a ratio. Regenerate samples a new phrasing. |

Training data is procedurally generated: ~24k mobile frames (forms, lists, carts, settings, card grids, empty states) with injected mistakes, labelled per layer by design-review heuristics (WCAG 2.x contrast, 44pt targets, and so on). Held-out scores are written to `models/metrics.json` and shown in the app's **Model card**.

## How the case study maps to the build

| Case study | In the prototype |
|---|---|
| Canvas is the source of truth | Frames live client-side; the API is stateless and only reads the frame you send. |
| Six message states | `Reply` class in `public/app.js`: queued (instant), thinking (named server steps), streaming, complete, error (one Retry), stopped (partial text kept, copyable). |
| Actions only when complete | Copy, Insert and Regenerate render only after `done`. |
| Batch, don't blink | Tokens buffer and flush to the DOM every 80ms. |
| Auto-scroll until you don't want it | Scrolling up releases the lock; new text collects behind a "N new lines" pill. |
| No fake typing delay | Tokens stream as soon as they're sampled. **Slow network** in the top bar is a clearly labelled simulation for demoing states, off by default. |
| No silent truncation | The critic's context window is 24 layers. The attachment chip shows the real count ("24 of 31 layers") and lists dropped layers crossed out. |
| Canvas never blocked | You can select other frames mid-stream; the reply stays tied to the frame it was asked about. |
| Chips from real issues | Suggestion chips come from the critic's findings; on a clean frame the row is empty. |
| Three surfaces | Docked resizable panel (340px min), ⌘K / Ctrl+K quick-ask overlay anchored to the selected frame, full-screen takeover on mobile. |
| Access | Answer announced once via a polite live region when it settles; focus moves to the new turn on send and back to the composer on completion; everything is keyboard reachable, including attaching a frame from the composer; `prefers-reduced-motion` removes the cursor blink and dot pulse. |

## Trust, agency and care

Kiln is a design-review copilot, so each principle below is applied the way it makes sense for one.

| Principle | In the prototype |
|---|---|
| **Visual anchors** | Each finding is its own block, with a functional icon and a colour-coded rule per issue type (contrast, hierarchy, target, type, spacing, empty state). Blocks are separated by dividers. Measurements and patches render as code-coloured `SPEC` and `PATCH` blocks, visibly different from prose, and hex values carry swatches. |
| **Tone indicator** | A Concise / Balanced / Technical / Plain control in the panel header, with a one-line "what to expect". Plain uses a separate plain-language register the narrator was trained on; Technical adds a spec line per claim. |
| **Voice & screen readers** | The server sends a speech-shaped version of every block (`2.6:1` becomes "2.6 to 1", `#5C5549` becomes "a dark warm grey", `"cta-primary"` becomes "the cta primary layer"). Screen readers read that version, the live region announces it once the answer settles, and **Read aloud** speaks it. |
| **Confidence & sources** | Each claim is labelled **Standard** (WCAG), **Convention** (a guideline with credible alternatives) or **Judgment** (the critic's opinion), with a calibrated band (Verified / High / Medium / Low). Low-confidence judgments get a spoken hedge. Inline `[n]` citations highlight the layer and open **Check facts**, which re-measures every claim against the canvas as it is *now*, and says when the frame has changed since the answer. Wording is always marked as generated; numbers never are. |
| **Alternative views** | "Where people disagree" lists the other defensible positions for each issue: APCA (WCAG 3 draft, computed live) next to WCAG 2.x contrast; WCAG 24px vs HIG 44pt vs Material 48dp; and the case where equal-weight buttons are the *more* honest design (consent screens). |
| **Also considered** | Issues the critic scored below 50%, and citations that measurement rejected, are listed as "not claimed" instead of being hidden or asserted. |
| **Rules** | Plain-language constraints ("under 50 words", "don't change the colours", "only contrast", "top 2 issues", "one sentence each", "no jargon") are parsed, echoed back as **Rule active** pills, kept until removed, and checked on every reply (for example "✓ 38 / 40 words"). The narrator is steered away from proposing colours when colour changes are ruled out. |
| **Edit this part** | Every block has an Edit menu (also offered when you select text inside it): Rephrase, Shorter, Plainer, More technical, **Not an issue** (Kiln stops flagging that layer) or edit the text yourself. Only that block regenerates. |
| **Nudge disclosure** | Emphatic phrases ("Thumbs will miss it") get a wavy underline and a framing note: the measurement is the fact, the framing is persuasion. Alternates disclose why the first option is listed first. |
| **Friction by design** | Patches with more than two changes open a review where each change can be unticked before anything touches the canvas. Undo is always available. |
| **Care routing** | Crisis language pauses the design work and points to 988 (US) and findahelpline.com, without assessment questions or confidentiality claims. Stress gets a short acknowledgement and a smaller answer: one issue, concise. Life decisions get deliberate friction and a reflective question instead of advice. Questions about Kiln's feelings get an honest answer: it's software. These responses are written by people and labelled that way, never generated. Detection is a keyword safety net plus the intent model; it will miss things. |
| **Time-aware** | A gentle, dismissible note after an hour, or after midnight. It can be snoozed or turned off. Nothing is tracked beyond the tab. |
| **Memory** | Every memory toggle is off by default. "What Kiln remembers" shows the current state in plain words, and **Forget everything now** wipes it. Memory lives only in the browser. |
| **Privacy** | Emails, phone and card numbers are masked on the device before sending (the critic only needs text length); the server masks again, logs nothing, and sends `Cache-Control: no-store`. "Help improve Kiln" is opt-in and shows exactly what would be shared. |
| **Dialect equity** | The intent model is trained with informal, regional and non-native phrasings as first-class examples, and evaluated on two hand-written held-out sets (textbook vs informal) with parity reported in the model card. |
| **Localisation** | Platform (Web px / iOS pt / Android dp) changes units and which guideline is cited first; spelling follows US or UK English. |

## Run locally

```bash
pip install -r requirements.txt uvicorn
uvicorn api.index:app --reload --port 8000
# open http://localhost:8000
```

## Retrain the models

```bash
pip install -r ml/requirements.txt
python ml/train.py           # ~15–20 min on a laptop CPU; writes models/*.onnx + metrics.json
python ml/train.py --quick   # smoke test
python ml/train.py --only language   # retrain intent + narrator only (~3 min)
```

## Deploy to Vercel

1. Go to [vercel.com/new](https://vercel.com/new) and import this GitHub repo.
2. Leave the framework preset as **Other**. No build command, no env vars.
3. Deploy. `public/` is served statically; `api/index.py` becomes a Python function (FastAPI) and `vercel.json` routes `/api/*` to it. Every push to `main` redeploys.

PyTorch isn't a runtime dependency. The deployed function only needs `fastapi`, `numpy` and `onnxruntime` (about 100 MB installed, well under Vercel's function limit), and the four ONNX files total about 4 MB.

## Repo layout

```
api/index.py        FastAPI app (Vercel function): /api/frames, /api/analyze, /api/chat, /api/model
kiln/               shared, torch-free code: features, colour math, engine, fix proposals, demo frames
ml/                 PyTorch: synthetic data, models, training + ONNX export
models/             exported ONNX models, vocab, metrics
public/             frontend (vanilla HTML/CSS/JS)
```

## Limits

This is a prototype. The critic learns from synthetic frames and heuristic labels, so it's only as good as its teacher and may misread layouts unlike anything it trained on. The narrator is small and template-trained: it phrases findings, it doesn't reason about them. Kiln is a concept, not a shipped product.

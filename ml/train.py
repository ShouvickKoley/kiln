"""Train Kiln's three models in PyTorch and export them to ONNX.

    python ml/train.py            # full run (~2-4 min on a laptop CPU)
    python ml/train.py --quick    # smoke test

Outputs to models/: critic.onnx, intent.onnx, narrator_init.onnx, narrator_step.onnx,
meta.json (vocab + label names) and metrics.json (held-out scores).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ml"))

from corpus import EVAL_INFORMAL, EVAL_STANDARD, KINDS, MODES, SEVERITIES, narration_corpus, question_corpus  # noqa: E402
from models import Critic, IntentNet, Narrator, NarratorInit, NarratorStep, bce_masked  # noqa: E402
from synth import build_dataset  # noqa: E402

from kiln.features import ISSUES, MAX_LAYERS, N_FEATURES  # noqa: E402
from kiln.text import BOS, EOS, FOCI, HASH_DIM, INTENTS, PAD, hash_features, tokenize  # noqa: E402

OUT = ROOT / "models"
torch.manual_seed(0)
np.random.seed(0)
random.seed(0)


def f1(pred, true):
    tp = (pred & true).sum()
    p = tp / max(pred.sum(), 1)
    r = tp / max(true.sum(), 1)
    return float(2 * p * r / max(p + r, 1e-9)), float(p), float(r)


# ---------------------------------------------------------------------------
def train_critic(n_train, n_val, epochs):
    print(f"[critic] generating {n_train}+{n_val} synthetic frames…")
    Xtr, Mtr, Ytr = build_dataset(n_train, seed=1)
    Xva, Mva, Yva = build_dataset(n_val, seed=99)
    Xtr, Mtr, Ytr = map(torch.from_numpy, (Xtr, Mtr, Ytr))
    Xva_t, Mva_t = torch.from_numpy(Xva), torch.from_numpy(Mva)

    model = Critic(N_FEATURES, len(ISSUES))
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=2e-3, total_steps=epochs * (len(Xtr) // 128 + 1))
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(len(Xtr))
        tot = 0.0
        for i in range(0, len(Xtr), 128):
            idx = perm[i : i + 128]
            x, m, y = Xtr[idx], Mtr[idx], Ytr[idx]
            ll, fl = model(x, m)
            loss = bce_masked(ll, y, m) + F.binary_cross_entropy_with_logits(fl, y.max(1).values)
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
            tot += loss.item() * len(idx)
        model.eval()
        with torch.no_grad():
            ll, fl = model(Xva_t, Mva_t)
        fp = (torch.sigmoid(fl).numpy() > 0.5)
        ft = Yva.max(1) > 0.5
        macro = np.mean([f1(fp[:, k], ft[:, k])[0] for k in range(len(ISSUES))])
        print(f"[critic] epoch {ep+1:2d}/{epochs}  loss {tot/len(Xtr):.4f}  val frame-F1 {macro:.3f}")

    # final metrics
    lp = (torch.sigmoid(ll).numpy() > 0.5) & (Mva[:, :, None] > 0)
    lt = Yva > 0.5
    metrics = {"frame": {}, "layer": {}}
    for k, name in enumerate(ISSUES):
        metrics["frame"][name] = dict(zip(("f1", "precision", "recall"), f1(fp[:, k], ft[:, k])))
        metrics["layer"][name] = dict(zip(("f1", "precision", "recall"), f1(lp[:, :, k], lt[:, :, k])))
    metrics["frame_macro_f1"] = float(np.mean([v["f1"] for v in metrics["frame"].values()]))
    metrics["layer_macro_f1"] = float(np.mean([v["f1"] for v in metrics["layer"].values()]))
    metrics["n_train"], metrics["n_val"] = n_train, n_val
    metrics["params"] = sum(p.numel() for p in model.parameters())

    torch.onnx.export(
        model, (Xva_t[:1], Mva_t[:1]), OUT / "critic.onnx",
        input_names=["x", "mask"], output_names=["layer_logits", "frame_logits"],
        dynamic_axes={"x": {0: "b"}, "mask": {0: "b"}, "layer_logits": {0: "b"}, "frame_logits": {0: "b"}},
        opset_version=17, dynamo=False,
    )
    return metrics


# ---------------------------------------------------------------------------
def train_intent(epochs):
    rows = question_corpus(seed=0, per=40)
    random.shuffle(rows)
    X = torch.from_numpy(np.stack([hash_features(q) for q, _, _ in rows]))
    yi = torch.tensor([i for _, i, _ in rows])
    yf = torch.tensor([f for _, _, f in rows])
    n_val = len(rows) // 8
    model = IntentNet(HASH_DIM, len(INTENTS), len(FOCI))
    opt = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=1e-4)
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(len(rows) - n_val) + n_val
        for i in range(0, len(perm), 64):
            idx = perm[i : i + 64]
            a, b = model(X[idx])
            loss = F.cross_entropy(a, yi[idx]) + F.cross_entropy(b, yf[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        a, b = model(X[:n_val])
    acc_i = (a.argmax(1) == yi[:n_val]).float().mean().item()
    acc_f = (b.argmax(1) == yf[:n_val]).float().mean().item()
    print(f"[intent] val intent acc {acc_i:.3f}  focus acc {acc_f:.3f}  ({len(rows)} questions)")

    def held_out(rows_):
        x = torch.from_numpy(np.stack([hash_features(q) for q, _, _ in rows_]))
        with torch.no_grad():
            pa, pb = model(x)
        ti = torch.tensor([INTENTS.index(i) for _, i, _ in rows_])
        tf = torch.tensor([FOCI.index(f) for _, _, f in rows_])
        return {"intent_acc": (pa.argmax(1) == ti).float().mean().item(),
                "focus_acc": (pb.argmax(1) == tf).float().mean().item(), "n": len(rows_),
                "misses": [q for (q, _, _), ok in zip(rows_, (pa.argmax(1) == ti).tolist()) if not ok]}
    parity = {"standard": held_out(EVAL_STANDARD), "informal": held_out(EVAL_INFORMAL)}
    print(f"[intent] hand-written held-out  standard {parity['standard']['intent_acc']:.3f}/{parity['standard']['focus_acc']:.3f}"
          f"  informal {parity['informal']['intent_acc']:.3f}/{parity['informal']['focus_acc']:.3f}")
    torch.onnx.export(model, (X[:1],), OUT / "intent.onnx", input_names=["x"], output_names=["intent_logits", "focus_logits"],
                      dynamic_axes={"x": {0: "b"}}, opset_version=17, dynamo=False)
    return {"intent_acc": acc_i, "focus_acc": acc_f, "n_questions": len(rows), "parity": parity}


# ---------------------------------------------------------------------------
def cond_vec(mode, kind, sev):
    v = np.zeros(len(MODES) + len(KINDS) + len(SEVERITIES), dtype=np.float32)
    v[mode] = 1
    v[len(MODES) + kind] = 1
    v[len(MODES) + len(KINDS) + sev] = 1
    return v


def train_narrator(epochs):
    rows = narration_corpus()
    vocab = [PAD, BOS, EOS] + sorted({t for *_, s in rows for t in tokenize(s)})
    stoi = {t: i for i, t in enumerate(vocab)}
    seqs = [[stoi[BOS]] + [stoi[t] for t in tokenize(s)] + [stoi[EOS]] for *_, s in rows]
    T = max(map(len, seqs))
    tok = torch.full((len(rows), T), stoi[PAD], dtype=torch.long)
    for i, s in enumerate(seqs):
        tok[i, : len(s)] = torch.tensor(s)
    cond = torch.from_numpy(np.stack([cond_vec(m, k, s) for m, k, s, _ in rows]))

    model = Narrator(len(vocab), cond.shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=4e-3)
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(len(rows))
        tot = 0.0
        for i in range(0, len(rows), 32):
            idx = perm[i : i + 32]
            x, y = tok[idx, :-1], tok[idx, 1:]
            # token dropout on inputs makes sampling a bit more robust
            drop = (torch.rand_like(x, dtype=torch.float) < 0.05) & (x != stoi[BOS])
            x = x.masked_fill(drop, stoi[PAD])
            lg = model(x, cond[idx])
            loss = F.cross_entropy(lg.reshape(-1, len(vocab)), y.reshape(-1), ignore_index=stoi[PAD])
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            tot += loss.item()
        if (ep + 1) % 20 == 0:
            print(f"[narrator] epoch {ep+1}/{epochs}  loss {tot / (len(rows) / 32):.3f}")
    model.eval()
    init, step = NarratorInit(model), NarratorStep(model)
    c1 = cond[:1]
    h0 = init(c1)
    torch.onnx.export(init, (c1,), OUT / "narrator_init.onnx", input_names=["cond"], output_names=["h"], opset_version=17, dynamo=False)
    torch.onnx.export(step, (torch.tensor([stoi[BOS]]), h0, c1), OUT / "narrator_step.onnx",
                      input_names=["tok", "h", "cond"], output_names=["logits", "h_out"], opset_version=17, dynamo=False)
    print(f"[narrator] vocab {len(vocab)}  templates {len(rows)}  final loss {tot / (len(rows) / 32):.3f}")
    return vocab, {"vocab": len(vocab), "templates": len(rows), "final_loss": tot / (len(rows) / 32)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--only", choices=["narrator", "language"], help="retrain just the narrator (or intent + narrator), keep the critic")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    t0 = time.time()
    if a.only:
        metrics = json.loads((OUT / "metrics.json").read_text())
        if a.only == "language":
            metrics["intent"] = train_intent(12)
        vocab, narr = train_narrator(160)
        meta = json.loads((OUT / "meta.json").read_text())
        meta.update(vocab=vocab, intents=INTENTS, modes=MODES)
        (OUT / "meta.json").write_text(json.dumps(meta))
        metrics["narrator"] = narr
        (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2))
        return
    critic = train_critic(2000 if a.quick else 24000, 500 if a.quick else 3000, 2 if a.quick else 18)
    intent = train_intent(3 if a.quick else 12)
    vocab, narr = train_narrator(10 if a.quick else 160)
    meta = {"issues": ISSUES, "intents": INTENTS, "foci": FOCI, "modes": MODES, "kinds": KINDS,
            "severities": SEVERITIES, "vocab": vocab, "max_layers": MAX_LAYERS, "n_features": N_FEATURES}
    (OUT / "meta.json").write_text(json.dumps(meta))
    metrics = {"critic": critic, "intent": intent, "narrator": narr, "torch": torch.__version__,
               "train_seconds": round(time.time() - t0, 1)}
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps({k: metrics["critic"][k] for k in ("frame_macro_f1", "layer_macro_f1", "params")}, indent=2))


if __name__ == "__main__":
    main()

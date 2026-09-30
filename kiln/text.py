"""Text utilities shared by training and inference: a hashed n-gram featuriser for the
intent model, and a word tokenizer / detokenizer for the narrator."""
from __future__ import annotations

import re
import zlib

import numpy as np

INTENTS = ["diagnose", "fix", "alternates", "audit", "describe", "clarify", "personal"]
FOCI = ["none", "low_contrast", "weak_hierarchy", "small_tap_target", "small_text", "crowded", "missing_guidance"]
HASH_DIM = 4096


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9:' ]+", " ", s.lower()).strip()


def hash_features(text: str) -> np.ndarray:
    """Bag of word uni/bi-grams + char trigrams, hashed into HASH_DIM buckets, L2-normalised."""
    v = np.zeros(HASH_DIM, dtype=np.float32)
    t = _norm(text)
    words = t.split()
    grams = words + [a + "_" + b for a, b in zip(words, words[1:])]
    padded = f"  {t}  "
    grams += ["#" + padded[i : i + 3] for i in range(len(padded) - 2)]
    for g in grams:
        v[zlib.crc32(g.encode()) % HASH_DIM] += 1.0
    n = np.linalg.norm(v)
    return v / n if n else v


# ---- narrator tokenisation -------------------------------------------------
TOKEN_RE = re.compile(r"<[a-z_]+>|[A-Za-z0-9'’\-]+|[.,:;()!?\"—]")
PAD, BOS, EOS = "<pad>", "<bos>", "<eos>"


def tokenize(s: str) -> list[str]:
    return TOKEN_RE.findall(s)


def join_token(prev: str | None, tok: str) -> str:
    """Return the text to append for `tok`, given the previous token (for spacing)."""
    if prev is None or prev == BOS:
        return tok
    if tok in ".,:;)!?":
        return tok
    if prev in "(\"" or prev == "—" or tok == "—":
        return tok if prev in "(\"" else " " + tok
    return " " + tok

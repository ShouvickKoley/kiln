"""PyTorch model definitions. Kept deliberately small so the ONNX exports ship inside a
Vercel function (a few MB total) and run in milliseconds on CPU."""
from __future__ import annotations

import math

import torch
import torch.nn as nn
import torch.nn.functional as F


class MaskedSelfAttention(nn.Module):
    """Plain multi-head self-attention with an additive padding mask (ONNX-friendly)."""

    def __init__(self, d: int, heads: int):
        super().__init__()
        self.h, self.dk = heads, d // heads
        self.qkv = nn.Linear(d, 3 * d)
        self.out = nn.Linear(d, d)

    def forward(self, x, mask):  # x [B,L,D], mask [B,L] (1 = real layer)
        B, L, D = x.shape
        q, k, v = self.qkv(x).view(B, L, 3, self.h, self.dk).permute(2, 0, 3, 1, 4)
        att = (q @ k.transpose(-1, -2)) / math.sqrt(self.dk)  # [B,h,L,L]
        att = att + (1.0 - mask)[:, None, None, :] * -1e4
        att = att.softmax(-1)
        y = (att @ v).transpose(1, 2).reshape(B, L, D)
        return self.out(y), att.mean(1)


class Block(nn.Module):
    def __init__(self, d, heads, drop=0.1):
        super().__init__()
        self.ln1, self.ln2 = nn.LayerNorm(d), nn.LayerNorm(d)
        self.att = MaskedSelfAttention(d, heads)
        self.ff = nn.Sequential(nn.Linear(d, 2 * d), nn.GELU(), nn.Linear(2 * d, d))
        self.drop = nn.Dropout(drop)

    def forward(self, x, mask):
        a, w = self.att(self.ln1(x), mask)
        x = x + self.drop(a)
        x = x + self.drop(self.ff(self.ln2(x)))
        return x, w


class Critic(nn.Module):
    """Set-transformer over a frame's layers.

    Each layer attends to every other layer in the frame (a CTA is only 'weak' relative
    to its neighbours), then a per-layer head scores each issue. Frame-level scores are
    a masked max over layers (multiple-instance learning), so the layer that drives a
    frame-level finding is, by construction, the one we cite.
    """

    def __init__(self, n_features: int, n_issues: int, d: int = 96, heads: int = 4, depth: int = 3):
        super().__init__()
        self.inp = nn.Sequential(nn.Linear(n_features, d), nn.GELU(), nn.Linear(d, d))
        self.blocks = nn.ModuleList([Block(d, heads) for _ in range(depth)])
        self.ln = nn.LayerNorm(d)
        self.head = nn.Sequential(nn.Linear(d, d), nn.GELU(), nn.Linear(d, n_issues))

    def forward(self, x, mask):
        h = self.inp(x)
        for b in self.blocks:
            h, _ = b(h, mask)
        layer_logits = self.head(self.ln(h))  # [B,L,I]
        masked = layer_logits + (1.0 - mask)[:, :, None] * -1e4
        frame_logits = masked.max(1).values  # [B,I]
        return layer_logits, frame_logits


class IntentNet(nn.Module):
    """Hashed n-gram MLP (fastText-style) with two heads: what the user wants (intent)
    and which issue they're asking about (focus)."""

    def __init__(self, in_dim: int, n_intents: int, n_foci: int, hidden: int = 128):
        super().__init__()
        self.body = nn.Sequential(nn.Linear(in_dim, hidden), nn.ReLU(), nn.Dropout(0.2))
        self.intent = nn.Linear(hidden, n_intents)
        self.focus = nn.Linear(hidden, n_foci)

    def forward(self, x):
        h = self.body(x)
        return self.intent(h), self.focus(h)


class Narrator(nn.Module):
    """Conditional word-level GRU language model. Condition = (mode, finding kind,
    severity); numbers and names are slot tokens filled in after decoding."""

    def __init__(self, vocab: int, cond_dim: int, emb: int = 64, hidden: int = 192):
        super().__init__()
        self.emb = nn.Embedding(vocab, emb)
        self.c2h = nn.Linear(cond_dim, hidden)
        self.c2x = nn.Linear(cond_dim, 32)
        self.cell = nn.GRUCell(emb + 32, hidden)
        self.out = nn.Linear(hidden, vocab)
        self.hidden = hidden

    def init_state(self, cond):
        return torch.tanh(self.c2h(cond))

    def step(self, tok, h, cond):
        x = torch.cat([self.emb(tok), torch.tanh(self.c2x(cond))], -1)
        h = self.cell(x, h)
        return self.out(h), h

    def forward(self, tokens, cond):  # teacher forcing: tokens [B,T]
        h = self.init_state(cond)
        logits = []
        for t in range(tokens.shape[1]):
            lg, h = self.step(tokens[:, t], h, cond)
            logits.append(lg)
        return torch.stack(logits, 1)


class NarratorStep(nn.Module):
    """Export wrapper: a single decode step (the loop runs in numpy at inference so the
    server can stream each token the moment it's sampled)."""

    def __init__(self, n: Narrator):
        super().__init__()
        self.n = n

    def forward(self, tok, h, cond):
        return self.n.step(tok, h, cond)


class NarratorInit(nn.Module):
    def __init__(self, n: Narrator):
        super().__init__()
        self.n = n

    def forward(self, cond):
        return self.n.init_state(cond)


def bce_masked(logits, target, mask):
    loss = F.binary_cross_entropy_with_logits(logits, target, reduction="none").mean(-1)
    return (loss * mask).sum() / mask.sum().clamp(min=1)

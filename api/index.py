"""Kiln API — FastAPI app served as a single Vercel Python function.

Routes
  GET  /api/health
  GET  /api/frames          demo canvas
  GET  /api/model           model card: metrics from training
  POST /api/analyze         {frame}                         -> findings + citations + chips
  POST /api/chat            {frame, message, seed?, pace_ms?, fail?}  -> NDJSON stream
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse  # noqa: E402
from typing import Literal  # noqa: E402

from pydantic import BaseModel, Field  # noqa: E402

from kiln.engine import Engine  # noqa: E402
from kiln.samples import sample_frames  # noqa: E402

# Privacy: nothing is logged or persisted server-side, and nothing should be cached in between.
NO_STORE = {"Cache-Control": "no-store", "X-Kiln-Retention": "none"}

app = FastAPI(title="Kiln", docs_url="/api/docs", openapi_url="/api/openapi.json")
_engine: Engine | None = None


def engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = Engine()
    return _engine


class AnalyzeIn(BaseModel):
    frame: dict
    dismissed: list[dict] = []


class ChatIn(BaseModel):
    frame: dict
    message: str = Field(min_length=1, max_length=500)
    seed: int = 0
    pace_ms: int = Field(0, ge=0, le=120)  # demo control: throttle to make streaming states visible
    fail: bool = False                     # demo control: simulate a dropped model connection
    tone: Literal["concise", "balanced", "technical", "plain"] = "balanced"
    constraints: list[dict] = []           # rules the person set earlier; Kiln echoes the active set back
    dismissed: list[dict] = []             # findings the person marked "not an issue"
    platform: Literal["web", "ios", "android"] = "web"
    spelling: Literal["en-US", "en-GB"] = "en-US"
    only_issue: str | None = None          # re-generate just one block ("Edit this part")


def _validate(frame: dict):
    if not isinstance(frame.get("layers"), list) or not frame.get("w") or not frame.get("h"):
        raise HTTPException(422, "frame needs w, h and layers")
    if len(frame["layers"]) > 400:
        raise HTTPException(413, "frame too large")


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/frames")
def frames():
    return {"frames": sample_frames()}


@app.get("/api/model")
def model_card():
    e = engine()
    return {"metrics": e.metrics, "issues": e.meta["issues"], "intents": e.meta["intents"],
            "max_layers": e.meta["max_layers"], "vocab": len(e.vocab), "modes": e.meta.get("modes")}


@app.post("/api/analyze")
def analyze(body: AnalyzeIn):
    _validate(body.frame)
    from kiln.privacy import mask_frame
    frame, _ = mask_frame(body.frame)
    return JSONResponse(engine().analyze(frame, body.dismissed), headers=NO_STORE)


@app.post("/api/chat")
def chat(body: ChatIn):
    _validate(body.frame)
    e = engine()

    def gen():
        try:
            n = 0
            for ev in e.chat(body.frame, body.message, seed=body.seed, pace_ms=body.pace_ms, tone=body.tone,
                             constraints=body.constraints, dismissed=body.dismissed, platform=body.platform,
                             spelling=body.spelling, only_issue=body.only_issue):
                if body.fail and ev["type"] == "token":
                    n += 1
                    if n > 6:
                        yield json.dumps({"type": "error", "text": "Couldn't reach the model"}) + "\n"
                        return
                yield json.dumps(ev) + "\n"
        except Exception as exc:  # surface, don't swallow
            yield json.dumps({"type": "error", "text": "Couldn't reach the model", "detail": str(exc)[:200]}) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson",
                             headers={**NO_STORE, "X-Accel-Buffering": "no"})


# Local dev convenience: serve the static frontend from the same process.
PUBLIC = ROOT / "public"


@app.get("/")
def index():
    return FileResponse(PUBLIC / "index.html")


@app.get("/{path:path}")
def static(path: str):
    f = (PUBLIC / path).resolve()
    if PUBLIC in f.parents and f.is_file():
        return FileResponse(f)
    raise HTTPException(404)

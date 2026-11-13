"""Serve the screen files. No sign-in, no paid calls."""

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI()
_live_calls = 0


def _daily_cap() -> int:
    raw = os.environ.get("NODAL_DAILY_LIVE_RUNS")
    if raw is None or not str(raw).strip():
        return 10
    try:
        value = int(str(raw).strip())
    except ValueError:
        return 10
    return 10 if value < 0 else value


def _sample_path(pid: str) -> Path:
    root = (ROOT / "data" / "samples").resolve()
    path = (root / f"{pid}.json").resolve()
    if path.parent != root or not path.is_file():
        raise HTTPException(status_code=404, detail="No session file for this id.")
    return path


def _texts(pid: str) -> dict:
    data = json.loads(_sample_path(pid).read_text(encoding="utf-8"))
    texts = data.get("ai_texts") or {}
    return texts if isinstance(texts, dict) else {}


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/session/{pid}")
def session(pid: str):
    return json.loads(_sample_path(pid).read_text(encoding="utf-8"))


@app.get("/api/ai/{pid}")
def ai_stored(pid: str):
    return {"ai_texts": _texts(pid), "live": False}


@app.post("/api/ai/{pid}")
def ai_live(pid: str):
    global _live_calls
    texts = _texts(pid)
    if os.environ.get("NODAL_LIVE_AI") != "1":
        return {"ai_texts": texts, "live": False}
    if _live_calls >= _daily_cap():
        raise HTTPException(status_code=429, detail="Daily live run cap reached.")
    _live_calls += 1
    raise HTTPException(status_code=503, detail="Live AI is not configured.")


app.mount("/data", StaticFiles(directory=ROOT / "data"), name="data")
app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")

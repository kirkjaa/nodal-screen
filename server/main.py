"""Serve the screen files. No sign-in, no paid calls."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI()


@app.get("/api/health")
def health():
    return {"ok": True}


app.mount("/data", StaticFiles(directory=ROOT / "data"), name="data")
app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")

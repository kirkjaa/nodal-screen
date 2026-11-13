"""Checks for the screen shell. Exits 0 only when every step passes."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "session.schema.json"
SAMPLES = ROOT / "data" / "samples"
SCAN_ROOTS = [ROOT / "web", ROOT / "data", ROOT / "docs"]
SKIP = {ROOT / "docs" / "CONTRACT.md"}
NODE_PATH = "C:/Users/User/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules"
ALLOW = (
    "clinicians review and diagnose",
    "clinician reviews and diagnoses",
    "does not diagnose",
    "not a diagnosis",
    "not yet validated",
    "to be validated",
    "Sarcopenia: revised European consensus on definition and diagnosis",
    "Asian Working Group for Sarcopenia: 2019 Consensus Update on Sarcopenia Diagnosis and Treatment",
)
PATTERNS = (
    re.compile(r"diagnos(?:e|es|is|ing|tic)", re.I),
    re.compile(r"\bvalidated\b", re.I),
    re.compile(r"clinically proven", re.I),
    re.compile(r"\bcertified\b", re.I),
    re.compile(r"\bFDA\b", re.I),
    re.compile(r"CE[- ]mark", re.I),
    re.compile(r"AI[- ]powered", re.I),
    re.compile(r"revolutionary", re.I),
    re.compile(r"seamless", re.I),
    re.compile(r"cutting[- ]edge", re.I),
    re.compile("\u2014"),
)


def step_pytest() -> None:
    subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, check=True)


def step_schema() -> None:
    import json
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    for path in sorted(SAMPLES.glob("*.json")):
        if path.name == "index.json":
            continue
        instance = json.loads(path.read_text(encoding="utf-8"))
        errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.path))
        if errors:
            for err in errors:
                print(f"{path.name}: {list(err.path)} {err.message}")
            raise SystemExit(1)


def _scrub(text: str) -> str:
    for phrase in ALLOW:
        text = re.sub(re.escape(phrase), " ", text, flags=re.I)
    return text


def step_honesty() -> None:
    hits = 0
    for folder in SCAN_ROOTS:
        for path in folder.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".html", ".js", ".css", ".json", ".md", ".py"}:
                continue
            if path.resolve() in SKIP:
                continue
            text = _scrub(path.read_text(encoding="utf-8"))
            for i, line in enumerate(text.splitlines(), start=1):
                if any(pattern.search(line) for pattern in PATTERNS):
                    print(f"{path.relative_to(ROOT)}:{i}: {line.strip()}")
                    hits += 1
    if hits:
        raise SystemExit(1)


def step_shots() -> None:
    if not shutil_which("node"):
        print("node not on PATH; screenshots skipped")
        return
    env = os.environ.copy()
    env["NODE_PATH"] = NODE_PATH
    env["SHOTS_BASE"] = "http://127.0.0.1:8099"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.main:app", "--port", "8099"],
        cwd=ROOT,
        env=env,
    )
    try:
        _wait_health()
        subprocess.run(["node", str(ROOT / "scripts" / "shots.cjs")], cwd=ROOT, env=env, check=True)
    finally:
        proc.kill()
        proc.wait(timeout=10)


def _wait_health() -> None:
    import urllib.request
    for _ in range(40):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8099/api/health", timeout=1) as res:
                if res.status == 200:
                    return
        except Exception:
            time.sleep(0.25)
    raise SystemExit("server did not start")


def shutil_which(name: str):
    from shutil import which
    return which(name)


def main() -> None:
    step_pytest()
    step_schema()
    step_honesty()
    step_shots()
    print("VERIFY OK")


if __name__ == "__main__":
    main()

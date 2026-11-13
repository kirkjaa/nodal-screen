"""Prompt, checks, and the dry-run script. No network."""

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from screen.ai_check import check
from screen.ai_prompt import facts, build_prompt
from scripts import ai_texts

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {
    "display_name", "group", "age_band", "sex", "metrics", "flags",
    "qc", "suggested_pathway", "suggested_pathway_label", "review",
}
METRIC_KEYS = {
    "id", "side", "value", "unit", "status", "norm_mean", "norm_z", "cutoff",
}
CUTOFF_KEYS = {"op", "threshold", "met", "source"}


def base_session():
    return {
        "participant": {
            "pid": "SYN-T-0001",
            "display_name": "Test",
            "group": "adult",
            "age_y": 70,
            "age_band": "seventies",
            "sex": "F",
        },
        "video": "clip.mp4",
        "capture_path": "D:/secret/file.json",
        "qc": {"status": "ok", "confidence": "high", "notes": [], "keypoint_confidence": 0.91},
        "tasks": {"gait": {"metrics": []}},
        "flags": [],
        "suggested_pathway": {"code": "ROUTINE", "reason_flag_ids": []},
        "review": None,
        "ai_texts": {},
    }


def test_facts_keep_only_the_letter_fields():
    session = json.loads((ROOT / "data" / "samples" / "SYN-C-0102.json").read_text(encoding="utf-8"))
    session["video"] = "clip.mp4"
    session["capture_path"] = "D:/secret/file.json"
    got = facts(session)
    assert set(got) <= ALLOWED
    assert "review" not in got
    blob = json.dumps(got)
    assert "clip.mp4" not in blob
    assert "secret" not in blob
    assert "SYN-C-0102" not in blob
    assert got["display_name"]
    assert set(got["qc"]) == {"status", "confidence", "notes"}
    assert set(got["flags"][0]) == {"title", "evidence", "sources"}
    assert set(got["metrics"][0]) == METRIC_KEYS
    heel = next(row for row in got["metrics"] if row["id"] == "heel_first_share" and row["side"] == "left")
    assert set(heel["cutoff"]) == CUTOFF_KEYS
    assert heel["cutoff"]["source"] == "NODAL screening rule"
    assert heel["cutoff"]["met"] is True
    names = [name for flag in got["flags"] for name in flag["sources"]]
    assert "NODAL screening rule" in names
    assert all("CONTRACT" not in name for name in names)

    session["review"] = {
        "clinician": "CLN-01",
        "decision": "confirm",
        "pathway": "WCV_DEV_REVIEW",
        "note": "",
        "at": "2026-11-13T00:00:00Z",
    }
    assert facts(session)["review"]["decision"] == "confirm"


def test_insufficient_prompt_asks_only_for_a_recapture_letter():
    session = json.loads((ROOT / "data" / "samples" / "SYN-C-0104.json").read_text(encoding="utf-8"))
    system, user = build_prompt(session, "family_letter")
    assert "recapture letter" in system
    assert "only" in system
    assert "repeated" in system
    assert "one line on why" not in system
    assert json.loads(user) == facts(session)
    full, _ = build_prompt(base_session(), "family_letter")
    assert "one line on why" in full
    assert "recapture letter" not in full


def test_check_catches_honesty_length_and_invented_numbers():
    session = base_session()
    assert any("honesty" in item for item in check("This visit is a diagnosis.", session))
    assert any("honesty" in item for item in check("The tool is validated.", session))
    assert check("This is screening. It does not diagnose.", session) == []
    assert check("This screen is not yet validated.", session) == []
    assert any("word limit" in item for item in check("word " * 161, session))
    assert check("word " * 160, session) == []
    assert any("word limit" in item for item in check("word " * 141, session, "clinician_brief"))
    assert any(item.startswith("number not in facts: 9.99") for item in check("Speed 9.99.", session))
    assert check("Age 70.", session) == []
    assert any("71" in item for item in check("Age 71.", session))
    assert check("The walk is 10 m, the chair is 5 times, the turn is 3 m.", session) == []
    session["flags"] = [{"title": "One", "evidence": "watch", "source_ids": ["nodal-rule"]}] * 4
    assert check("There are 4 flags.", session) == []


def test_run_without_env_exits_before_importing_genai(tmp_path):
    package = tmp_path / "google"
    (package / "genai").mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "genai" / "__init__.py").write_text("raise SystemExit('IMPORTED')\n", encoding="utf-8")
    env = os.environ.copy()
    env.pop("GOOGLE_CLOUD_PROJECT", None)
    env.pop("NODAL_AI_MODEL", None)
    env["PYTHONPATH"] = str(tmp_path) + os.pathsep + str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "ai_texts.py"), "--run", "--price-in", "1", "--price-out", "1"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    combined = proc.stdout + proc.stderr
    assert proc.returncode != 0
    assert "IMPORTED" not in combined
    assert "GOOGLE_CLOUD_PROJECT" in combined


def test_live_config_and_client_match_the_card(monkeypatch):
    recorded = {}

    class Config:
        def __init__(self, **kwargs):
            recorded["config"] = kwargs

    class Client:
        def __init__(self, **kwargs):
            recorded["client"] = kwargs

    fake_genai = SimpleNamespace(Client=Client, types=SimpleNamespace(GenerateContentConfig=Config))
    monkeypatch.setitem(sys.modules, "google", SimpleNamespace(genai=fake_genai))
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
    ai_texts.live_config("system text")
    ai_texts.make_client("proj-1")
    assert recorded["config"]["temperature"] == 0.2
    assert recorded["config"]["response_mime_type"] == "application/json"
    assert recorded["config"]["system_instruction"] == "system text"
    assert recorded["client"] == {"enterprise": True, "project": "proj-1", "location": "global"}


def _client(text: str):
    class Models:
        def generate_content(self, model, contents, config):
            return SimpleNamespace(text=text)

    return SimpleNamespace(models=Models())


def test_fake_client_stores_a_clean_reply(tmp_path, monkeypatch):
    path = tmp_path / "SYN-T.json"
    path.write_text(json.dumps(base_session()), encoding="utf-8")
    monkeypatch.setattr(ai_texts, "live_config", lambda system: object())
    reply = json.dumps({
        "en": "The capture was a screening. A clinician decides.",
        "ar": "هذا فحص.",
    })
    ai_texts.store_from_client(path, _client(reply), "test-model", 20)
    saved = json.loads(path.read_text(encoding="utf-8"))
    for kind in ("family_letter", "clinician_brief"):
        body = saved["ai_texts"][kind]
        assert body["status"] == "stored-sample"
        assert body["model"] == "test-model"
        assert body["en"].startswith("The capture")
        assert body["ar"]
        assert body["generated_at"]


def test_fake_reply_with_diagnose_is_not_stored(tmp_path, monkeypatch):
    path = tmp_path / "SYN-T.json"
    original = json.dumps(base_session())
    path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(ai_texts, "live_config", lambda system: object())
    reply = json.dumps({"en": "Please diagnose this.", "ar": "نص"})
    ai_texts.store_from_client(path, _client(reply), "test-model", 20)
    assert path.read_text(encoding="utf-8") == original


def test_dry_run_prints_totals_and_does_not_write(tmp_path, capsys):
    samples = tmp_path / "samples"
    samples.mkdir()
    path = samples / "SYN-T.json"
    path.write_text(json.dumps(base_session()), encoding="utf-8")
    before = path.read_bytes()
    code = ai_texts.main([
        "--dry-run", "--price-in", "1", "--price-out", "1", "--samples", str(samples),
    ])
    assert code == 0
    assert path.read_bytes() == before
    out = capsys.readouterr().out
    assert "dry run, no model call" in out
    assert "TOTAL files=1 tokens_in=" in out
    assert "--- system ---" in out
    assert "--- user ---" in out

"""Session and stored-text API. Live drafting is stubbed and makes no outbound call."""

import re
import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import server.main as main

ROOT = Path(__file__).resolve().parents[1]
client = TestClient(main.app)


@pytest.fixture(autouse=True)
def _reset_live(monkeypatch):
    monkeypatch.delenv("NODAL_LIVE_AI", raising=False)
    monkeypatch.delenv("NODAL_DAILY_LIVE_RUNS", raising=False)
    main._live_calls = 0


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"ok": True}


def test_known_session():
    res = client.get("/api/session/SYN-C-0101")
    assert res.status_code == 200
    assert res.json()["participant"]["pid"] == "SYN-C-0101"


def test_unknown_session():
    res = client.get("/api/session/NOT-A-PERSON")
    assert res.status_code == 404


def test_flag_off_returns_stored_texts():
    stored = client.get("/api/ai/SYN-C-0101")
    assert stored.status_code == 200
    assert stored.json() == {"ai_texts": {}, "live": False}
    res = client.post("/api/ai/SYN-C-0101")
    assert res.status_code == 200
    assert res.json() == {"ai_texts": {}, "live": False}
    assert main._live_calls == 0


def test_live_flag_is_offline(monkeypatch):
    monkeypatch.setenv("NODAL_LIVE_AI", "1")
    monkeypatch.setenv("NODAL_DAILY_LIVE_RUNS", "3")

    def blocked(*_args, **_kwargs):
        raise AssertionError("outbound")

    monkeypatch.setattr(socket, "create_connection", blocked)
    res = client.post("/api/ai/SYN-C-0101")
    assert res.status_code == 503
    assert "not configured" in res.text.lower()
    assert main._live_calls == 1
    assert "http://" not in (ROOT / "server" / "main.py").read_text(encoding="utf-8")


def test_cap_stops_at_the_limit(monkeypatch):
    monkeypatch.setenv("NODAL_LIVE_AI", "1")
    monkeypatch.setenv("NODAL_DAILY_LIVE_RUNS", "1")
    first = client.post("/api/ai/SYN-A-0201")
    second = client.post("/api/ai/SYN-A-0201")
    third = client.post("/api/ai/SYN-C-0101")
    assert first.status_code == 503
    assert second.status_code == 429
    assert third.status_code == 429
    assert main._live_calls == 1


def test_default_cap_is_ten(monkeypatch):
    monkeypatch.setenv("NODAL_LIVE_AI", "1")
    for _ in range(10):
        assert client.post("/api/ai/SYN-C-0101").status_code == 503
    assert client.post("/api/ai/SYN-C-0101").status_code == 429
    assert main._live_calls == 10


def test_deploy_files_hold_no_secrets():
    deploy = (ROOT / "deploy.ps1").read_text(encoding="utf-8")
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    server = (ROOT / "server" / "main.py").read_text(encoding="utf-8")
    for text in (deploy, docker, server):
        assert "quest-dev" not in text
        assert "nodal3d.com" not in text
    assert not re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", deploy)
    assert "gs://" not in deploy
    assert "asia-southeast1" in deploy
    assert "nodal-screen" in deploy
    assert "NODAL_LIVE_AI=0" in deploy
    assert "python:3.12-slim" in docker
    assert "USER " in docker
    assert "--host 0.0.0.0" in docker

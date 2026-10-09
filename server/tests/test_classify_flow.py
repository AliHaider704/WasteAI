# File: server/tests/test_classify_flow.py
"""Classify flow: cache miss, hit, uncertain, hazard, errors never cached."""
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import cache, mapper
from app.main import app
from app.orchestrator import AllSourcesFailed, Orchestrator
from app.ratelimit import ip_limiter
from app.routes import classify as classify_route


class _Src:
    def __init__(self, labels):
        self.labels, self.calls = labels, 0

    async def classify(self, data):
        self.calls += 1
        return {"ok": bool(self.labels), "top": self.labels}


class _Off:
    enabled = False

    def status(self):
        return "disabled"


def _png(color) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture()
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(ip_limiter, "check", lambda ip: 0)
    box = {}

    def install(labels):
        src = _Src(labels)
        box["src"] = src
        orch = Orchestrator(src, _Off(), _Off())
        monkeypatch.setattr(classify_route, "get_orchestrator", lambda a: orch)
        return src

    box["install"] = install
    with TestClient(app) as c:
        box["client"] = c
        yield box


def _post(c, color=(10, 200, 30), lang="en"):
    return c.post(f"/api/v1/classify?lang={lang}", files={"image": ("a.png", _png(color), "image/png")})


def test_miss_then_hit(env):
    src = env["install"]([("plastic bottle", 0.95)])
    first = _post(env["client"])
    second = _post(env["client"])
    assert first.status_code == second.status_code == 200
    assert src.calls == 1
    a, b = first.json(), second.json()
    assert a["request_id"] != b["request_id"]
    assert a["category"] == b["category"]
    assert isinstance(b["elapsed_ms"], int)
    assert all(isinstance(x["elapsed_ms"], int) and x["elapsed_ms"] >= 0 for x in a["sources"])
    assert all(x["elapsed_ms"] is None for x in b["sources"])


def test_uncertain(env):
    env["install"]([("bottle", 0.30)])  # glass vs plastics: no group fallback
    body = _post(env["client"], (1, 2, 3)).json()
    assert body["status"] == "uncertain" and body["category"] is None


def test_hazard(env):
    assert "battery" in mapper.map_labels([("battery", 0.9)])
    body = _post(env["client"], (9, 9, 9)).json() if env["install"]([("battery", 0.9)]) else {}
    assert body["hazard"] is True
    assert body["guidance"] and body["guidance"]["warnings"]


def test_error_not_cached(env, monkeypatch):
    env["install"]([])  # no source answers -> all_sources_failed
    r = _post(env["client"], (5, 5, 5))
    assert r.status_code == 502 and r.json()["error"]["code"] == "all_sources_failed"
    src = env["install"]([("plastic bottle", 0.95)])
    r2 = _post(env["client"], (5, 5, 5))
    assert r2.status_code == 200 and src.calls == 1


def test_arabic_error_from_contract(env):
    env["install"]([])
    r = _post(env["client"], (7, 7, 7), "ar")
    assert r.json()["error"]["message"].startswith("تعذّر")


def test_startup_purges(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "p.db"))
    called = []

    async def fake():
        called.append(1)
        return 0

    monkeypatch.setattr(cache, "purge_expired", fake)
    with TestClient(app):
        pass
    assert called == [1]


def test_all_failed_exception_type():
    assert issubclass(AllSourcesFailed, Exception)

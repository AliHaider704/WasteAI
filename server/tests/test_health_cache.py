# File: server/tests/test_health_cache.py
"""A32: /health cache window, no-store, no secrets, HEAD and query strings never give 422."""
from fastapi.testclient import TestClient

from app.main import app
from app.routes import health as health_mod

c = TestClient(app)


def test_query_string_and_head_are_not_422():
    health_mod.clear_cache()
    assert c.get("/api/v1/health?x=1&lang=zz").status_code == 200
    assert c.head("/api/v1/health").status_code == 200


def test_no_store_and_no_secrets():
    health_mod.clear_cache()
    r = c.get("/api/v1/health")
    assert r.headers["cache-control"] == "no-store"
    body = r.json()
    assert set(body) == {"status", "version", "sources"}
    low = r.text.lower()
    assert "key" not in low and "/home" not in low


def test_cached_within_window(monkeypatch):
    health_mod.clear_cache()
    calls = []
    orch = health_mod.get_orchestrator(app)
    real = orch.statuses
    monkeypatch.setattr(orch, "statuses", lambda: calls.append(1) or real())
    c.get("/api/v1/health")
    c.get("/api/v1/health")
    assert len(calls) == 1
    health_mod._cache["at"] -= 10  # window expired
    c.get("/api/v1/health")
    assert len(calls) == 2

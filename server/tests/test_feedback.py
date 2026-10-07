# File: server/tests/test_feedback.py
"""Feedback hardening: issued ids only, one per id, catalog check, 10/min per IP."""
import asyncio
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import cache
from app.main import app
from app.ratelimit import IPLimiter
from app.routes import feedback as fb


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "f.db"))
    monkeypatch.setattr(fb, "feedback_limiter", IPLimiter(10, 60.0))
    with TestClient(app) as c:
        yield c


def _post(c, rid, cat="glass", lang="en"):
    return c.post(f"/api/v1/feedback?lang={lang}",
                  json={"request_id": rid, "correct_category_id": cat})


def _issue(rid):
    asyncio.run(cache.record_issued(rid))


def _rows():
    conn = sqlite3.connect(cache.db_path())
    try:
        return conn.execute("SELECT request_id, correct_category_id FROM feedback").fetchall()
    finally:
        conn.close()


def test_unknown_id_422(client):
    r = _post(client, "nope")
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"
    assert _rows() == []


def test_issued_id_stored(client):
    _issue("abc")
    assert _post(client, "abc").status_code == 204
    assert _rows() == [("abc", "glass")]


def test_duplicate_is_204_and_first_wins(client):
    _issue("dup")
    assert _post(client, "dup", "glass").status_code == 204
    assert _post(client, "dup", "paper").status_code == 204
    assert _rows() == [("dup", "glass")]


def test_unknown_category_422(client):
    _issue("c1")
    assert _post(client, "c1", "not_a_category").status_code == 422
    assert _rows() == []


def test_expired_id_422(client):
    _issue("old")
    conn = cache.connect()
    conn.execute("UPDATE issued SET ts=ts-?", (cache.TTL_SECONDS + 10,))
    conn.commit()
    conn.close()
    assert _post(client, "old").status_code == 422


def test_11th_request_429_with_retry_after(client):
    codes = [_post(client, f"x{i}").status_code for i in range(10)]
    assert codes == [422] * 10
    r = _post(client, "x10")
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 1


def test_error_message_arabic(client):
    r = _post(client, "nope", lang="ar")
    assert r.status_code == 422
    assert any("؀" <= ch <= "ۿ" for ch in r.json()["error"]["message"])

# File: server/tests/test_logging.py
"""Structured logging: JSON shape, no IP, client sink sanitizing and limit."""
import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.logging_setup import JSONFormatter, clean
from app.main import app
from app.ratelimit import IPLimiter
from app.routes import log as log_route


@pytest.fixture(autouse=True)
def _fresh_limiter(monkeypatch):
    monkeypatch.setattr(log_route, "log_limiter", IPLimiter(20, 60.0))


def _lines(caplog, logger):
    fmt = JSONFormatter()
    return [json.loads(fmt.format(r)) for r in caplog.records if r.name == logger]


def test_clean_strips_control_characters():
    assert clean("a\nb\x00c\u2028d", 50) == "a b c d"
    assert len(clean("x" * 500, 200)) == 200


def test_request_line_has_fields_and_no_ip(caplog):
    caplog.set_level(logging.INFO)
    TestClient(app).get("/api/v1/health")
    line = _lines(caplog, "wasteai.access")[-1]
    assert line["event"] == "request" and line["route"] == "/api/v1/health" and line["status"] == 200
    assert {"ts", "level", "request_id", "elapsed_ms"} <= set(line)
    raw = json.dumps(line).lower()
    assert "testclient" not in raw and "127.0.0.1" not in raw


def test_client_log_204_and_sanitized(caplog):
    caplog.set_level(logging.INFO)
    r = TestClient(app).post(
        "/api/v1/log",
        json={"level": "error", "event": "render_failed", "detail": "bad\nline\x00" + "y" * 400},
    )
    assert r.status_code == 204
    line = _lines(caplog, "wasteai.client")[-1]
    assert line["origin"] == "client" and line["client_event"] == "render_failed"
    assert "\n" not in line["detail"] and len(line["detail"]) <= 200


@pytest.mark.parametrize("body", [
    {"level": "fatal", "event": "x"},
    {"level": "info", "event": "Bad Event!"},
    {"level": "info"},
])
def test_client_log_rejects_bad_body(body):
    assert TestClient(app).post("/api/v1/log", json=body).status_code == 422


def test_client_log_rate_limit():
    c = TestClient(app)
    codes = [c.post("/api/v1/log", json={"level": "info", "event": "ping"}).status_code for _ in range(21)]
    assert codes[:20] == [204] * 20 and codes[20] == 429

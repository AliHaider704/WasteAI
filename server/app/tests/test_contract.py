# server/tests/test_contract.py
"""Stub responses must match the contract shapes (ARCHITECTURE sections 3-4)."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
ERR_KEYS = {"code", "message", "request_id"}


def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and set(body["sources"]) == {"local_onnx", "azure", "reciclapi"}
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "camera=(self)" in r.headers["permissions-policy"]


def test_categories_shape():
    r = client.get("/api/v1/categories?lang=ar")
    assert r.status_code == 200
    assert r.json()["version"] == 1 and isinstance(r.json()["categories"], list)


def test_classify_ok():
    r = client.post("/api/v1/classify", files={"image": ("a.png", PNG, "image/png")})
    assert r.status_code == 200
    b = r.json()
    assert b["status"] == "ok" and b["category"]["id"] == "plastic_pet"
    assert b["agreement"] in {"full", "partial", "none", "single_source"}
    assert len(b["request_id"]) > 10


def test_classify_unsupported_type():
    r = client.post("/api/v1/classify", files={"image": ("a.txt", b"hello world!!", "text/plain")})
    assert r.status_code == 415
    assert set(r.json()["error"]) == ERR_KEYS and r.json()["error"]["code"] == "unsupported_type"


def test_classify_too_large():
    big = b"\xff\xd8\xff" + b"\x00" * (2 * 1024 * 1024)
    r = client.post("/api/v1/classify", files={"image": ("a.jpg", big, "image/jpeg")})
    assert r.status_code == 413 and r.json()["error"]["code"] == "image_too_large"


def test_classify_missing_file_and_bad_lang():
    assert client.post("/api/v1/classify").status_code == 422
    r = client.get("/api/v1/categories?lang=fr")
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"


def test_error_message_localized():
    r = client.post("/api/v1/classify?lang=ar", files={"image": ("a.txt", b"x" * 20, "text/plain")})
    assert r.json()["error"]["message"].startswith("استخدم")


def test_feedback():
    ok = client.post("/api/v1/feedback", json={"request_id": "x", "correct_category_id": "glass"})
    assert ok.status_code == 204
    assert client.post("/api/v1/feedback", json={}).status_code == 422


def test_openapi_file_valid_if_present():
    spec = Path(__file__).resolve().parents[2] / "contract" / "openapi.yaml"
    if not spec.exists():
        pytest.skip("contract/openapi.yaml not present yet")
    import yaml
    from openapi_spec_validator import validate_spec

    validate_spec(yaml.safe_load(spec.read_text(encoding="utf-8")))

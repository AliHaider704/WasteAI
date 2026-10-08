# File: server/tests/test_health_paths.py
"""A22: self-tests, fallbacks and quota guard for the local and cloud paths (no network)."""
import asyncio

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import orchestrator as orch_mod
from app import quota
from app.main import app
from app.orchestrator import AllSourcesFailed, Orchestrator
from app.sources.vision_azure import VisionAzure
from app.sources.vision_local import LocalModelError, VisionLocal
from app.sources.vision_reciclapi import VisionReciclAPI

LABELS = ["a", "b", "c"]


class _In:
    name, shape = "x", [1, 3, 224, 224]


class _Sess:
    def __init__(self, out):
        self.out = out

    def get_inputs(self):
        return [_In()]

    def run(self, *_):
        return [np.asarray(self.out, dtype=np.float32)]


def _local(out):
    return VisionLocal(None, LABELS, session=_Sess(out))


def test_model_missing():
    m = VisionLocal(None, LABELS)
    with pytest.raises(LocalModelError):
        m.load()
    assert m.selftest()["reason"] == "model_not_loaded" and m.health["status"] == "down"


def test_selftest_ok():
    h = _local([[0.2, 0.3, 0.5]]).selftest()
    assert h["status"] == "up" and h["reason"] == "ok" and h["latency_ms"] is not None


def test_wrong_output_size():
    assert _local([[0.5, 0.5]]).selftest()["reason"] == "output_size_mismatch"


def test_nan_output():
    h = _local([[0.1, float("nan"), 0.3]]).selftest()
    assert h["reason"] == "nan_output" and h["status"] == "down"


def test_inference_error_has_no_path():
    class Boom(_Sess):
        def run(self, *_):
            raise RuntimeError("/secret/path")

    h = VisionLocal(None, LABELS, session=Boom(0)).selftest()
    assert h["reason"] == "inference_error:RuntimeError" and "/" not in h["reason"]


def _azure(handler):
    a = VisionAzure("https://x.test", "k")
    a._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return a


@pytest.fixture()
def free_quota(monkeypatch):
    monkeypatch.setattr(quota, "try_acquire", lambda: True)
    monkeypatch.setattr(quota, "exhausted", lambda: False)


def test_azure_401(free_quota):
    a = _azure(lambda r: httpx.Response(401))
    r = asyncio.run(a.classify(b"x"))
    assert not r.ok and r.error == "http_401"


def test_azure_timeout(free_quota):
    def h(request):
        raise httpx.ReadTimeout("slow")

    r = asyncio.run(_azure(h).classify(b"x"))
    assert not r.ok and r.error == "timeout"


def test_azure_quota_exhausted(monkeypatch):
    monkeypatch.setattr(quota, "exhausted", lambda: True)
    monkeypatch.setattr(quota, "try_acquire", lambda: False)
    a = _azure(lambda r: httpx.Response(200, json={}))
    assert asyncio.run(a.classify(b"x")).error == "quota"
    assert a.selftest()["status"] == "quota"


def test_azure_deep_check_once_per_hour(free_quota):
    calls = []

    def h(request):
        calls.append(1)
        return httpx.Response(200, json={"tagsResult": {"values": [{"name": "glass", "confidence": 0.9}]}})

    a = _azure(h)
    first = asyncio.run(a.deep_check())
    second = asyncio.run(a.deep_check())
    assert first["status"] == "up" and not first["cached"] and second["cached"] and len(calls) == 1


class _Src:
    def __init__(self, labels, delay=0.0):
        self.labels, self.delay = labels, delay

    async def classify(self, data):
        await asyncio.sleep(self.delay)
        return {"ok": bool(self.labels), "top": self.labels}


class _Az:
    enabled = True

    def __init__(self, src):
        self.classify = src.classify

    def status(self):
        return "up"


def _orch(local, azure):
    return Orchestrator(local, _Az(azure), VisionReciclAPI())


def _run(o):
    return asyncio.run(o.run(b"x", "en", "rid"))


def test_both_down_gives_502():
    with pytest.raises(AllSourcesFailed):
        _run(_orch(_Src([]), _Src([])))


def test_one_down_gives_single_source():
    body = _run(_orch(_Src([]), _Src([("plastic bottle", 0.95)])))
    assert body["agreement"] == "single_source" and body["category"]


def test_slow_source_skipped(monkeypatch):
    monkeypatch.setattr(orch_mod, "TIMEOUT", 0.05)
    body = _run(_orch(_Src([("plastic bottle", 0.95)], delay=1.0), _Src([("plastic bottle", 0.95)])))
    assert body["agreement"] == "single_source"
    assert [s["ok"] for s in body["sources"]].count(False) == 1


def test_health_deep_loopback_only(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "h.db"))
    with TestClient(app) as outside:
        assert outside.get("/api/v1/health/deep").status_code == 404
        assert outside.get("/api/v1/health").json()["sources"]["local_onnx"] in ("up", "down")
    from app.routes import health as health_route

    monkeypatch.setattr(health_route, "LOOPBACK", {"testclient"})  # TestClient's peer name
    with TestClient(app) as inside:
        r = inside.get("/api/v1/health/deep")
        assert r.status_code == 200 and {"local_onnx", "azure"} <= set(r.json())

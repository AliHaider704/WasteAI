# File: server/tests/test_vision_llm.py
"""LLM tiebreaker: flag off sends nothing, consent needed, hazard untouched, quota cap."""
import asyncio

import pytest

from app import db, quota
from app.orchestrator import Orchestrator
from app.sources.vision_llm import VisionLLM, parse_labels


class _Src:
    def __init__(self, labels):
        self.labels = labels

    async def classify(self, data):
        return {"ok": bool(self.labels), "top": self.labels}


class _Off:
    enabled = False

    def status(self):
        return "disabled"


class _FakeLLM:
    name = "llm"

    def __init__(self, enabled, labels):
        self.enabled, self.labels, self.calls = enabled, labels, 0

    def status(self):
        return "up" if self.enabled else "disabled"

    async def classify(self, data):
        self.calls += 1
        return {"ok": True, "top": self.labels}


@pytest.fixture(autouse=True)
def _db(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(db, "_conn", None)


def _run(local, llm, allow):
    orch = Orchestrator(_Src(local), _Off(), _Off(), llm)
    return asyncio.run(orch.run(b"x", "en", "rid", allow))


UNCLEAR = [("bottle", 0.30)]  # glass vs plastics: uncertain on its own


def test_flag_off_sends_nothing():
    llm = _FakeLLM(False, [("glass", 0.9)])
    assert _run(UNCLEAR, llm, True)["status"] == "uncertain"
    assert llm.calls == 0


def test_flag_on_without_consent_sends_nothing():
    llm = _FakeLLM(True, [("glass", 0.9)])
    _run(UNCLEAR, llm, False)
    assert llm.calls == 0


def test_flag_on_with_consent_called_when_uncertain():
    llm = _FakeLLM(True, [("glass bottle", 0.9)])
    body = _run(UNCLEAR, llm, True)
    assert llm.calls == 1
    assert any(s["name"] == "llm" for s in body["sources"])


def test_hazard_result_never_changed():
    llm = _FakeLLM(True, [("glass bottle", 0.9)])
    body = _run([("battery", 0.9)], llm, True)
    assert llm.calls == 0
    assert body["hazard"] is True and body["guidance"]["warnings"]


def test_quota_cap_returns_quota_without_error(monkeypatch):
    llm = VisionLLM(True, "k", "m", daily_cap=1)

    class _Boom:
        async def post(self, *a, **k):
            raise AssertionError("network must not be reached")

    quota.llm_try_acquire(1)
    llm._client = _Boom()
    res = asyncio.run(llm.classify(b"x"))
    assert res.ok is False and llm.status() == "quota"


def test_disabled_source_status_and_parse():
    assert VisionLLM().status() == "disabled"
    assert [d["label"] for d in parse_labels("Plastic bottle, PET.\nLong sentence here: no")] == [
        "plastic bottle", "pet"]

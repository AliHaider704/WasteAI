# File: server/tests/test_sources_timing.py
"""A30: per-source elapsed_ms (int on a miss, null on a cache hit) and the reason list."""
import asyncio

from app import orchestrator
from app.schemas import SourceResult


class _Fake:
    def __init__(self, label, score, delay=0.0):
        self.label, self.score, self.delay = label, score, delay

    async def classify(self, data):
        await asyncio.sleep(self.delay)
        return {"ok": True, "top": [{"label": self.label, "score": self.score}]}


def _orch():
    o = orchestrator.Orchestrator.__new__(orchestrator.Orchestrator)
    o.sources = [("local_onnx", _Fake("plastic", 0.9, 0.02)), ("azure", _Fake("bottle", 0.8))]
    o.llm = None
    return o


def _run():
    return asyncio.run(_orch().run(b"x", "en", "rid-1"))


def test_elapsed_present_and_not_negative_on_miss():
    res = _run()
    assert res["sources"]
    for s in res["sources"]:
        assert isinstance(s["elapsed_ms"], int) and s["elapsed_ms"] >= 0
    assert res["sources"][0]["elapsed_ms"] >= 15  # the slow fake


def test_reason_is_list_of_strings_or_absent():
    res = _run()
    reason = res.get("reason", [])
    assert isinstance(reason, list) and all(isinstance(x, str) for x in reason)


def test_schema_allows_null():
    assert SourceResult(name="azure", ok=True).elapsed_ms is None
    assert SourceResult(name="azure", ok=True, elapsed_ms=5).elapsed_ms == 5

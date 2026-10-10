# File: server/tests/test_weighting.py
"""A39: static mode unchanged; reliability weights; cloud override; fit clamps."""
import json

from app import aggregator, weighting

GROUPS = aggregator.GROUP_OF


def _scores():
    return {"local_onnx": {"general_residual": 0.8, "paper": 0.2},
            "azure": {"glass": 0.9, "paper": 0.1}}


def test_static_mode_equals_base(monkeypatch):
    monkeypatch.delenv("WEIGHT_MODE", raising=False)
    w = weighting.source_weights(_scores(), {"local_onnx": 0.6, "azure": 0.4}, {"azure": 0.1}, GROUPS)
    assert w == {"local_onnx": 0.6, "azure": 0.4}
    assert weighting.cloud_override(_scores(), {"azure": 0.9}) == _scores()


def test_reliability_weights(monkeypatch, tmp_path):
    f = tmp_path / "rel.json"
    f.write_text(json.dumps({"sources": {"azure": {"_overall": 0.8, "glass": 0.9},
                                         "local_onnx": {"_overall": 0.4}}}))
    monkeypatch.setenv("WEIGHT_MODE", "reliability")
    monkeypatch.setenv("RELIABILITY_PATH", str(f))
    w = weighting.source_weights(_scores(), {"local_onnx": 0.4, "azure": 0.6}, {"azure": 0.5}, GROUPS)
    assert abs(w["azure"] - 0.6 * 0.9 * 0.5) < 1e-9  # group value x strength
    assert abs(w["local_onnx"] - 0.4 * 0.4) < 1e-9  # falls back to _overall
    monkeypatch.setenv("RELIABILITY_PATH", str(tmp_path / "missing.json"))
    w = weighting.source_weights(_scores(), {"local_onnx": 0.4, "azure": 0.6}, None, GROUPS)
    assert abs(w["azure"] - 0.6 * weighting.DEFAULT_REL) < 1e-9


def test_cloud_override_rules(monkeypatch):
    monkeypatch.setenv("WEIGHT_MODE", "reliability")
    assert list(weighting.cloud_override(_scores(), {"azure": 0.7})) == ["azure"]
    assert len(weighting.cloud_override(_scores(), {"azure": 0.3})) == 2  # cloud too weak
    flipped = {"local_onnx": {"glass": 0.9}, "azure": {"general_residual": 0.9}}
    assert weighting.cloud_override(flipped, {"azure": 0.9}) == flipped  # both must agree


def test_decide_cloud_wins_over_local_residual(monkeypatch):
    monkeypatch.setenv("WEIGHT_MODE", "reliability")
    monkeypatch.setenv("RELIABILITY_PATH", "/nonexistent.json")
    monkeypatch.setenv("W_LOCAL", "0.6")
    from app.config import get_settings
    get_settings.cache_clear()
    scores = {"local_onnx": {"general_residual": 0.9, "glass": 0.1}, "azure": {"glass": 0.95, "paper": 0.05}}
    d = aggregator.decide(scores, {"local_onnx": 0.9, "azure": 0.8})
    assert d.category_id == "glass" and d.status == "ok"
    get_settings.cache_clear()


def test_fit_clamps_and_needs_samples():
    samples = ([("azure", "glass", True)] * 10 + [("local_onnx", "plastics", False)] * 6
               + [("local_onnx", "paper", True)] * 2)
    t = weighting.fit(samples)
    assert t["sources"]["azure"]["glass"] == weighting.CAP  # 100% -> capped at 0.9
    assert t["sources"]["local_onnx"]["plastics"] == weighting.FLOOR  # 0% -> floor 0.2
    assert "paper" not in t["sources"]["local_onnx"]  # only 2 samples
    assert t["n"]["azure"]["_overall"] == 10

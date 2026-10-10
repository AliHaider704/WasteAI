# File: server/tests/test_learn_rules.py
"""A38: learner maths on an 8-row fixture; harvest budget; caption flag."""
import importlib.util
from pathlib import Path

from app.sources import vision_azure

ROOT = Path(__file__).resolve().parents[2]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


learn = _load("learn_tag_rules")
harvest = _load("harvest_tags")


def tg(*labels):
    return [{"label": lb, "score": 0.9} for lb in labels]


ROWS = ([{"file": f"g{i}", "truth": "glass", "tags": tg("jar", "indoor")} for i in range(4)]
        + [{"file": f"p{i}", "truth": "plastic_unknown", "tags": tg("bag", "indoor")} for i in range(4)])


def test_learns_specific_tags_and_skips_generic():
    rules = learn.learn(ROWS)
    assert set(rules["jar"]) == {"glass"} and rules["jar"]["glass"] > 0
    assert set(rules["bag"]) == {"plastic_unknown"}
    assert "indoor" not in rules  # lift 1.0: no information


def test_rare_tag_dropped():
    rows = ROWS + [{"file": "x", "truth": "glass", "tags": tg("rare")}] * 2
    assert "rare" not in learn.learn(rows)


def test_split_is_stable_and_about_80_20():
    names = [f"f{i}" for i in range(1000)]
    a = [learn.is_train(n) for n in names]
    assert a == [learn.is_train(n) for n in names]
    assert 700 < sum(a) < 900


def test_holdout_accuracy():
    rules = learn.learn(ROWS)
    test = [{"file": "t1", "truth": "glass", "tags": tg("jar")},
            {"file": "t2", "truth": "glass", "tags": tg("bag")},
            {"file": "t3", "truth": "glass", "tags": tg("zzz")}]
    r = learn.holdout(test, rules)
    assert r == {"photos": 3, "with_match": 2, "accuracy": 50.0}


def test_harvest_budget():
    c = harvest.load_counter(Path("/nonexistent"), "2026-10")
    assert harvest.budget_left(c) == 1500
    c = {"month": "2026-10", "month_count": 1400, "total": 2950}
    assert harvest.budget_left(c) == 50
    assert harvest.load_counter(Path("/nonexistent"), "2026-11")["month_count"] == 0


def test_caption_flag_default_off(monkeypatch):
    monkeypatch.delenv("AZURE_CAPTION", raising=False)
    assert vision_azure.caption_enabled() is False
    monkeypatch.setenv("AZURE_CAPTION", "true")
    assert vision_azure.caption_enabled() is True
    body = {"captionResult": {"text": "a plastic bottle on a table", "confidence": 0.81}}
    assert vision_azure.caption_label(body) == {"label": "a plastic bottle on a table", "score": 0.81}
    assert vision_azure.caption_label({}) is None

# File: server/tests/test_mapper_v2.py
"""A37: mapper v2 keeps evidence strength; old path unchanged with the flag off."""
from app import mapper, mapper_v2

RULES = {
    "bottle": {"plastic_pet": 0.5},
    "plastic bottle": {"plastic_pet": 1.0},
    "can": {"metal_aluminum": 1.0},
}


def test_weak_single_tag_stays_under_half():
    res = mapper_v2.map_labels_v2([("bottle", 0.4)], RULES)
    assert res.shares(0.5)["plastic_pet"] < 0.5
    assert mapper.map_labels([("bottle", 0.4)], RULES)["plastic_pet"] == 1.0  # the old problem


def test_two_agreeing_tags_rise():
    one = mapper_v2.map_labels_v2([("plastic bottle", 0.9)], RULES).shares(0.5)["plastic_pet"]
    both = mapper_v2.map_labels_v2([("plastic bottle", 0.9), ("bottle", 0.9)], RULES)
    two = both.shares(0.5)["plastic_pet"]
    assert two > one > 0.5


def test_unmapped_reported_and_not_counted():
    res = mapper_v2.map_labels_v2([("tableware", 0.95), ("can", 0.8)], RULES)
    assert res.unmapped == ["tableware"] and list(res.scores) == ["metal_aluminum"]
    assert res.used == {"can": "metal_aluminum"}


def test_mark_items_order_and_limit():
    top = [("tableware", 0.95), ("bottle", 0.6), ("indoor", 0.9), ("can", 0.9), ("zzz", 0.1)]
    items = mapper_v2.mark_items(top, RULES)
    assert [i["label"] for i in items] == ["can", "bottle", "tableware"]
    assert items[0] == {"label": "can", "score": 0.9, "mapped": True, "cat": "metal_aluminum"}
    assert items[2]["mapped"] is False and "cat" not in items[2]


def test_flag_default_off_and_k_env(monkeypatch):
    monkeypatch.delenv("MAPPER_V2", raising=False)
    assert mapper_v2.v2_enabled() is False
    monkeypatch.setenv("MAPPER_V2", "true")
    assert mapper_v2.v2_enabled() is True
    monkeypatch.setenv("MAP_K", "bad")
    assert mapper_v2.map_k() == mapper_v2.DEFAULT_K


def test_flag_off_path_equals_old_mapper(monkeypatch):
    from app import orchestrator
    monkeypatch.delenv("MAPPER_V2", raising=False)
    pairs = [("plastic bottle", 0.9), ("cup", 0.5)]
    assert orchestrator._score(pairs) == mapper.map_labels(pairs)
    monkeypatch.setenv("MAPPER_V2", "true")
    assert sum(orchestrator._score(pairs).values()) < 1.0


def test_evidence_cloud_share():
    local = mapper_v2.map_labels_v2([("can", 0.9)], RULES)
    cloud = mapper_v2.map_labels_v2([("can", 0.9)], RULES)
    ev = mapper_v2.evidence({"local_onnx": local, "azure": cloud},
                            {"local_onnx": 0.6, "azure": 0.4}, "metal_aluminum")
    assert ev == {"strength": 0.9, "cloud_share": 0.4}
    assert mapper_v2.evidence({}, {}, "x") is None

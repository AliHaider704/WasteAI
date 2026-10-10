# File: server/tests/test_mapper.py
import json

from app import mapper
from app.aggregator import GROUP_OF
from app.sources import vision_azure


def test_all_rule_files_load():
    rules = mapper.load_rules()
    assert len(rules) > 59
    reached = {c for w in rules.values() for c in w}
    assert set(GROUP_OF) <= reached, set(GROUP_OF) - reached


def test_every_rule_file_has_labels_key():
    for f in mapper.RULES_DIR.rglob("*.json"):
        if f.name == "_scale.json":
            continue
        assert "labels" in json.loads(f.read_text("utf-8")), f.name


def test_battery_maps_to_battery():
    scores = mapper.map_labels([("battery", 0.9)])
    assert scores and max(scores, key=scores.get) == "battery"


def test_azure_stoplist_drops_generic_tags_and_keeps_ten():
    body = {"tagsResult": {"values": [{"name": "indoor", "confidence": 0.99},
                                      {"name": "Table", "confidence": 0.98}]
                           + [{"name": f"item{i}", "confidence": 0.9 - i / 100} for i in range(12)]}}
    top = vision_azure.top_labels(body)
    names = [t["label"] for t in top]
    assert "indoor" not in names and "Table" not in names
    assert len(top) == 10 and names[0] == "item0"


def test_azure_labels_reach_mapper():
    body = {"tagsResult": {"values": [{"name": "indoor", "confidence": 0.99},
                                      {"name": "battery", "confidence": 0.8}]}}
    pairs = [(t["label"], t["score"]) for t in vision_azure.top_labels(body)]
    assert max(mapper.map_labels(pairs).items(), key=lambda kv: kv[1])[0] == "battery"

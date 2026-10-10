# File: server/tests/test_mapper_index.py
"""A44: inverted index equals the old regex loop; folder scale factors; speed."""
import json
import re
import time

from app import mapper


def old_weights(label, rules):
    key = label.strip().lower()
    if key in rules:
        return [rules[key]]
    hits = [k for k in rules if re.search(rf"\b{re.escape(k)}\b", key)]
    if not hits:
        return []
    longest = max(len(k) for k in hits)
    return [rules[k] for k in hits if len(k) == longest]


def test_index_matches_old_behaviour_on_real_rules():
    rules = mapper.load_rules()
    labels = ["plastic bottle", "a crushed soda can", "glass jar lid", "battery", "xyzzy thing",
              "wine glass", "old newspaper stack", "t-shirt", "milk carton box"]
    for lb in labels:
        assert mapper._weights(lb, rules) == old_weights(lb, rules), lb


def test_longest_match_wins():
    rules = {"bottle": {"glass": 0.4}, "plastic bottle": {"plastic_pet": 1.0}}
    assert mapper._weights("big plastic bottle", rules) == [{"plastic_pet": 1.0}]
    assert mapper._weights("bottle opener", rules) == [{"glass": 0.4}]


def test_word_boundary_not_substring():
    rules = {"can": {"metal_aluminum": 1.0}}
    assert mapper._weights("scan", rules) == []
    assert mapper._weights("a can", rules) == [{"metal_aluminum": 1.0}]


def test_folder_scale_factors(tmp_path):
    for folder, w in (("hand", 1.0), ("seed", 1.0), ("learned", 1.0)):
        d = tmp_path / folder
        d.mkdir()
        (d / "a.json").write_text(json.dumps({"labels": {f"{folder}only": {"glass": w},
                                                        "shared": {"glass": w}}}))
    (tmp_path / "_scale.json").write_text(json.dumps({"scale": {"hand": 1.0, "seed": 0.5, "learned": 0.25}}))
    rules = mapper._load(tmp_path)
    assert rules["handonly"]["glass"] == 1.0
    assert rules["seedonly"]["glass"] == 0.5
    assert rules["learnedonly"]["glass"] == 0.25
    assert abs(rules["shared"]["glass"] - 1.75) < 1e-9


def test_ten_labels_under_5ms_with_many_rules():
    rules = {f"word{i} thing{i % 7}": {"glass": 0.3} for i in range(5000)}
    rules["bottle"] = {"glass": 0.4}
    labels = [f"a bottle of word{i} thing{i % 7} stuff" for i in range(10)]
    mapper._weights(labels[0], rules)  # builds the index once
    t = time.perf_counter()
    for lb in labels:
        mapper._weights(lb, rules)
    assert (time.perf_counter() - t) * 1000 < 5

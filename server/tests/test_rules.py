# server/tests/test_rules.py
import json
from pathlib import Path

import pytest

from app.aggregator import GROUP_OF

RULES_DIR = Path(__file__).resolve().parents[1] / "data" / "label_rules"
FIXTURES = {
    "organic_food": "banana", "organic_garden": "leaves", "ewaste_small": "smartphone",
    "ewaste_large": "refrigerator", "battery": "battery", "textile": "clothes",
    "hazardous_chemical": "pesticide", "medical": "syringe", "wood": "plank",
    "construction": "concrete", "general_residual": "diaper",
}


def _load() -> dict[str, dict[str, float]]:
    rules: dict[str, dict[str, float]] = {}
    for f in sorted(RULES_DIR.glob("*.json")):
        for label, cats in json.loads(f.read_text(encoding="utf-8")).items():
            if label.startswith("_"):
                continue
            slot = rules.setdefault(label.lower(), {})
            for c, w in cats.items():
                slot[c] = slot.get(c, 0.0) + w
    return rules


def _score(labels: dict[str, float]) -> dict[str, float]:
    rules, out = _load(), {}
    for label, s in labels.items():
        for c, w in rules.get(label, {}).items():
            out[c] = out.get(c, 0.0) + w * s
    total = sum(out.values()) or 1.0
    return {c: v / total for c, v in out.items()}


def test_all_26_categories_reachable():
    reached = {c for cats in _load().values() for c in cats}
    assert set(GROUP_OF) <= reached, set(GROUP_OF) - reached


def test_rule_ids_are_valid():
    for cats in _load().values():
        assert set(cats) <= set(GROUP_OF)


@pytest.mark.parametrize("cat,label", FIXTURES.items())
def test_fixture_label_maps_to_category(cat, label):
    scores = _score({label: 0.9})
    assert max(scores, key=scores.get) == cat

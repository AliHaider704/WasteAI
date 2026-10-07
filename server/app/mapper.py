# File: server/app/mapper.py
import json
import os
import re
from functools import lru_cache
from pathlib import Path

RULES_DIR = Path(
    os.getenv("RULES_DIR", Path(__file__).resolve().parents[1] / "data" / "label_rules")
)


@lru_cache(maxsize=1)
def load_rules() -> dict[str, dict[str, float]]:
    """Merge all rule files: label -> {category_id: weight} (weights add up across files)."""
    rules: dict[str, dict[str, float]] = {}
    for f in sorted(RULES_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        for label, weights in (data.get("labels") or {}).items():
            slot = rules.setdefault(label.strip().lower(), {})
            for cid, w in weights.items():
                slot[cid] = slot.get(cid, 0.0) + float(w)
    return rules


def _weights(label: str, rules: dict) -> list[dict[str, float]]:
    key = label.strip().lower()
    if key in rules:
        return [rules[key]]
    hits = [k for k in rules if re.search(rf"\b{re.escape(k)}\b", key)]
    if not hits:
        return []
    longest = max(len(k) for k in hits)
    return [rules[k] for k in hits if len(k) == longest]


def map_labels(top: list[tuple[str, float]], rules: dict | None = None) -> dict[str, float]:
    """Raw labels -> {category_id: score}, normalized to sum 1. Empty if nothing matched."""
    rules = load_rules() if rules is None else rules
    scores: dict[str, float] = {}
    for label, s in top:
        for weights in _weights(label, rules):
            for cid, w in weights.items():
                scores[cid] = scores.get(cid, 0.0) + w * s
    total = sum(scores.values())
    return {c: v / total for c, v in scores.items()} if total > 0 else {}


def matching_labels(top: list[tuple[str, float]], category_id: str, rules: dict | None = None) -> list[str]:
    """Raw labels whose rules feed category_id (rule ids for the "why" list, no generated text)."""
    rules = load_rules() if rules is None else rules
    return [lb for lb, _ in top if any(category_id in w for w in _weights(lb, rules))]

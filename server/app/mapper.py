# File: server/app/mapper.py
import json
import os
import re
from functools import lru_cache
from pathlib import Path

RULES_DIR = Path(
    os.getenv("RULES_DIR", Path(__file__).resolve().parents[1] / "data" / "label_rules")
)
_TOKEN = re.compile(r"\w+")
_INDEX: dict[int, tuple[dict, dict]] = {}  # id(rules) -> (rules, word -> keys)


def _scales(root: Path) -> dict[str, float]:
    try:
        data = json.loads((root / "_scale.json").read_text("utf-8"))
        return {k: float(v) for k, v in data["scale"].items()}
    except (OSError, ValueError, KeyError):
        return {}


def _load(root: Path) -> dict[str, dict[str, float]]:
    """Merge rule files in every sub folder: label -> {category_id: weight}.

    Each folder's weights are multiplied by its factor in _scale.json (hand 1.0, seed 0.5,
    learned 0.5); files directly in the root count 1.0. Weights add up across files.
    """
    scale = _scales(root)
    rules: dict[str, dict[str, float]] = {}
    for f in sorted(root.rglob("*.json")):
        if f.name == "_scale.json":
            continue
        try:
            data = json.loads(f.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        rel = f.relative_to(root)
        factor = scale.get(rel.parts[0], 1.0) if len(rel.parts) > 1 else 1.0
        for label, weights in (data.get("labels") or {}).items():
            slot = rules.setdefault(label.strip().lower(), {})
            for cid, w in weights.items():
                slot[cid] = slot.get(cid, 0.0) + float(w) * factor
    return rules


@lru_cache(maxsize=1)
def load_rules() -> dict[str, dict[str, float]]:
    return _load(RULES_DIR)


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _index(rules: dict) -> dict[str, list[tuple[str, tuple[str, ...]]]]:
    """Inverted index: first word of a rule key -> [(key, key words)]; built once per rule set."""
    hit = _INDEX.get(id(rules))
    if hit is not None and hit[0] is rules:
        return hit[1]
    idx: dict[str, list[tuple[str, tuple[str, ...]]]] = {}
    for key in rules:
        words = tuple(_tokens(key))
        if words:
            idx.setdefault(words[0], []).append((key, words))
    if len(_INDEX) > 8:
        _INDEX.clear()
    _INDEX[id(rules)] = (rules, idx)
    return idx


def _contains(tokens: list[str], words: tuple[str, ...]) -> bool:
    n = len(words)
    return any(tuple(tokens[i:i + n]) == words for i in range(len(tokens) - n + 1))


def _weights(label: str, rules: dict) -> list[dict[str, float]]:
    """Exact label first; else every rule whose words occur in the label, longest wins."""
    key = label.strip().lower()
    if key in rules:
        return [rules[key]]
    tokens = _tokens(key)
    idx = _index(rules)
    hits = [(k, w) for t in set(tokens) for k, w in idx.get(t, ()) if _contains(tokens, w)]
    if not hits:
        return []
    longest = max(len(k) for k, _ in hits)
    return [rules[k] for k, _ in hits if len(k) == longest]


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

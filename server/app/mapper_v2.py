# File: server/app/mapper_v2.py
"""Mapper v2 (A37): keep evidence strength and report which tags were used (D-048).

Old map_labels() divides by the sum, so one weak tag becomes 100%. Here every category keeps its
raw mass (sum of rule weight x label score); a source's category score is mass / (total + K).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from app import mapper

DEFAULT_K = 0.5


def v2_enabled() -> bool:
    return os.getenv("MAPPER_V2", "false").strip().lower() in ("1", "true", "yes", "on")


def map_k() -> float:
    try:
        k = float(os.getenv("MAP_K", DEFAULT_K))
    except ValueError:
        return DEFAULT_K
    return k if k > 0 else DEFAULT_K


@dataclass
class MapResult:
    scores: dict[str, float] = field(default_factory=dict)  # category -> raw mass
    used: dict[str, str] = field(default_factory=dict)  # label -> category it fed most
    unmapped: list[str] = field(default_factory=list)  # labels with no rule
    contrib: dict[str, float] = field(default_factory=dict)  # label -> strongest contribution

    @property
    def total(self) -> float:
        return sum(self.scores.values())

    def strength(self) -> float:
        """Absolute mass of the strongest category, capped at 1."""
        return min(1.0, max(self.scores.values(), default=0.0))

    def shares(self, k: float | None = None) -> dict[str, float]:
        """Per-category scores for the aggregator: mass / (total mass + K); weak evidence stays low."""
        total = self.total
        if total <= 0:
            return {}
        k = map_k() if k is None else k
        return {c: m / (total + k) for c, m in self.scores.items()}


def map_labels_v2(top: list[tuple[str, float]], rules: dict | None = None) -> MapResult:
    rules = mapper.load_rules() if rules is None else rules
    res = MapResult()
    for label, s in top:
        found = mapper._weights(label, rules)
        if not found:
            res.unmapped.append(label)
            continue
        per_label: dict[str, float] = {}
        for weights in found:
            for cid, w in weights.items():
                per_label[cid] = per_label.get(cid, 0.0) + w * s
        for cid, v in per_label.items():
            res.scores[cid] = res.scores.get(cid, 0.0) + v
        best = max(per_label, key=lambda c: (per_label[c], c))
        if label not in res.used or per_label[best] > res.contrib[label]:
            res.used[label], res.contrib[label] = best, per_label[best]
    return res


def mark_items(top: list[tuple[str, float]], rules: dict | None = None, limit: int = 3) -> list[dict]:
    """Contract delta: items with `mapped` and `cat`; mapped first (by contribution), then unmapped."""
    res = map_labels_v2(top, rules)
    mapped = sorted(((lb, sc) for lb, sc in top if lb in res.used),
                    key=lambda t: -res.contrib[t[0]])
    rest = sorted(((lb, sc) for lb, sc in top if lb not in res.used), key=lambda t: -t[1])
    items = [{"label": lb, "score": round(sc, 4), "mapped": True, "cat": res.used[lb]}
             for lb, sc in mapped]
    items += [{"label": lb, "score": round(sc, 4), "mapped": False} for lb, sc in rest]
    return items[:limit]


def evidence(masses: dict[str, MapResult], weights: dict[str, float], winner: str | None) -> dict | None:
    """{"strength": 0..1, "cloud_share": 0..1} for the winning category, or None."""
    if not winner or not masses:
        return None
    total_w = sum(weights.get(n, 0.2) for n in masses) or 1.0
    shares = {n: (weights.get(n, 0.2) / total_w) * r.shares().get(winner, 0.0) for n, r in masses.items()}
    whole = sum(shares.values())
    cloud = sum(v for n, v in shares.items() if n != "local_onnx")
    strength = max((r.scores.get(winner, 0.0) for r in masses.values()), default=0.0)
    return {"strength": round(min(1.0, strength), 2),
            "cloud_share": round(cloud / whole, 2) if whole > 0 else 0.0}

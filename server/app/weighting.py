# File: server/app/weighting.py
"""Source weighting (A39, D-050): static (default) or reliability-aware, evidence-aware.

WEIGHT_MODE=static       weight = base[source]                       (old behaviour, W_* env)
WEIGHT_MODE=reliability  weight = base[source] x reliability[source][group of its top] x strength
Reliability comes from data/source_reliability.json, fitted by `scripts/replay.py --fit-reliability`
(never hand-written): floor 0.2, cap 0.9. Rule 3 (cloud_override): a strong cloud answer beats a
local "general_residual".
"""
from __future__ import annotations

import json
import os
from pathlib import Path

FLOOR, CAP, DEFAULT_REL, MIN_SAMPLES = 0.2, 0.9, 0.5, 5
STRONG = 0.5  # cloud strength needed for the override
MIN_STRENGTH = 0.05  # keeps one weak source from zeroing the sum
RESIDUAL = "general_residual"
_CACHE: dict[tuple[str, float], dict] = {}


def mode() -> str:
    return "reliability" if os.getenv("WEIGHT_MODE", "static").strip().lower() == "reliability" else "static"


def reliability_path() -> Path:
    return Path(os.getenv("RELIABILITY_PATH",
                          Path(__file__).resolve().parents[1] / "data" / "source_reliability.json"))


def load_reliability(path: Path | None = None) -> dict:
    p = path or reliability_path()
    try:
        key = (str(p), p.stat().st_mtime)
    except OSError:
        return {}
    if key not in _CACHE:
        try:
            _CACHE[key] = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            _CACHE[key] = {}
    return _CACHE[key]


def reliability_of(rel: dict, source: str, group: str) -> float:
    src = (rel.get("sources") or {}).get(source, {})
    return float(src.get(group, src.get("_overall", DEFAULT_REL)))


def _top(cats: dict[str, float]) -> str:
    return max(cats.items(), key=lambda kv: (kv[1], kv[0]))[0]


def source_weights(scores: dict[str, dict[str, float]], base: dict[str, float],
                   strengths: dict[str, float] | None = None,
                   group_of: dict[str, str] | None = None) -> dict[str, float]:
    """Weight for each source that answered. Static mode returns the base table unchanged."""
    if mode() != "reliability":
        return {n: base.get(n, 0.2) for n in scores}
    rel = load_reliability()
    out = {}
    for name, cats in scores.items():
        group = (group_of or {}).get(_top(cats), "other")
        s = max((strengths or {}).get(name, 1.0), MIN_STRENGTH)
        out[name] = max(base.get(name, 0.2) * reliability_of(rel, name, group) * s, 1e-6)
    return out


def cloud_override(scores: dict[str, dict[str, float]],
                   strengths: dict[str, float] | None = None) -> dict[str, dict[str, float]]:
    """Local says residual, cloud has a strong specific category: cloud alone decides.

    The opposite (cloud residual vs local specific) is not overridden: both must agree.
    """
    if mode() != "reliability" or "local_onnx" not in scores or "azure" not in scores:
        return scores
    if _top(scores["local_onnx"]) != RESIDUAL or _top(scores["azure"]) == RESIDUAL:
        return scores
    cloud = scores["azure"]
    strength = (strengths or {}).get("azure", cloud[_top(cloud)])
    if strength < STRONG:
        return scores
    return {k: v for k, v in scores.items() if k != "local_onnx"}


def fit(samples: list[tuple[str, str, bool]], min_n: int = MIN_SAMPLES) -> dict:
    """samples: (source, group of its top, top was right). -> reliability table with counts."""
    tot: dict[str, list[int]] = {}
    per: dict[tuple[str, str], list[int]] = {}
    for src, group, ok in samples:
        for bucket, key in ((tot, src), (per, (src, group))):
            c = bucket.setdefault(key, [0, 0])
            c[0] += bool(ok)
            c[1] += 1
    clamp = lambda r: round(min(CAP, max(FLOOR, r)), 3)  # noqa: E731
    sources: dict[str, dict[str, float]] = {}
    counts: dict[str, dict[str, int]] = {}
    for src, (hit, n) in tot.items():
        sources[src] = {"_overall": clamp(hit / n)}
        counts[src] = {"_overall": n}
    for (src, group), (hit, n) in per.items():
        if n >= min_n:
            sources[src][group] = clamp(hit / n)
            counts[src][group] = n
    return {"_path": "server/data/source_reliability.json", "sources": sources, "n": counts}

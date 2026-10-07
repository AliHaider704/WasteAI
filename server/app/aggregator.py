# File: server/app/aggregator.py
"""Combine per-source category scores into one decision (TECH-SPEC section 5)."""
from __future__ import annotations

from dataclasses import dataclass

WEIGHTS = {"local_onnx": 0.6, "azure": 0.4, "reciclapi": 0.2}
# Baseline values (A5/A7a, before A14): TEMPERATURE 1.0, OK_MIN 0.65,
# SINGLE_OK_MIN 0.80, HAZARD_MIN 0.35. Change only from field data
# (scripts/fit_temperature.py) and record before/after in DECISIONS.
TEMPERATURE = 1.0  # >1 softens the combined scores, <1 sharpens; 1.0 = off
OK_MIN = 0.65
SINGLE_OK_MIN = 0.80
HAZARD_MIN = 0.35
ALT_MIN = 0.05
GROUP_MIN = 0.65  # top-two combined score needed for a group fallback
FALLBACK_CAP = 0.79  # keeps the UI confidence word at "Medium" (High >= 0.80)

# Group fallback targets. Groups missing here (glass, e-waste, other) never fall back.
GROUP_DEFAULT = {
    "plastics": "plastic_unknown",
    "paper": "paper",
    "metals": "metal_other",
    "organic": "organic_food",
}

HAZARD_IDS = frozenset(
    {"battery", "hazardous_chemical", "medical", "ewaste_small", "ewaste_large"}
)

GROUP_OF: dict[str, str] = {
    **{c: "plastics" for c in (
        "plastic_pet", "plastic_hdpe", "plastic_pvc", "plastic_ldpe",
        "plastic_pp", "plastic_ps", "plastic_other", "plastic_unknown")},
    **{c: "paper" for c in ("paper", "cardboard", "carton_beverage")},
    "glass": "glass",
    **{c: "metals" for c in ("metal_aluminum", "metal_steel", "metal_other")},
    **{c: "organic" for c in ("organic_food", "organic_garden")},
    **{c: "e-waste" for c in ("ewaste_small", "ewaste_large", "battery")},
    **{c: "other" for c in (
        "textile", "hazardous_chemical", "medical", "wood",
        "construction", "general_residual")},
}


@dataclass(frozen=True)
class Decision:
    status: str  # "ok" | "uncertain"
    category_id: str | None
    confidence: float
    alternatives: list[tuple[str, float]]
    agreement: str  # full | partial | none | single_source
    hazard: bool
    hazard_id: str | None
    fallback: bool = False  # True when the answer is a group default


def _top_id(scores: dict[str, float]) -> str:
    return max(scores.items(), key=lambda kv: (kv[1], kv[0]))[0]


def combine(scores: dict[str, dict[str, float]]) -> dict[str, float]:
    """Weighted mean over the sources that answered (weights renormalized)."""
    total = sum(WEIGHTS.get(name, 0.2) for name in scores)
    out: dict[str, float] = {}
    for name, cats in scores.items():
        w = WEIGHTS.get(name, 0.2) / total
        for cat, val in cats.items():
            out[cat] = out.get(cat, 0.0) + w * val
    return out


def calibrate(scores: dict[str, float], temperature: float | None = None) -> dict[str, float]:
    """Temperature scaling on combined scores: p^(1/T), renormalized. T=1 is identity."""
    t = TEMPERATURE if temperature is None else temperature
    if t <= 0:
        raise ValueError("temperature must be positive")
    if t == 1.0 or not scores:
        return dict(scores)
    powered = {c: max(v, 1e-12) ** (1.0 / t) for c, v in scores.items()}
    total = sum(powered.values())
    return {c: v / total for c, v in powered.items()}


def group_fallback(ranked: list[tuple[str, float]]) -> tuple[str, float] | None:
    """Group default when the top two share a safe group; never for hazard ids."""
    if len(ranked) < 2:
        return None
    (a, sa), (b, sb) = ranked[0], ranked[1]
    if a in HAZARD_IDS or b in HAZARD_IDS:
        return None
    group = GROUP_OF.get(a)
    if group is None or group != GROUP_OF.get(b) or group not in GROUP_DEFAULT:
        return None
    total = sa + sb
    if total < GROUP_MIN:
        return None
    return GROUP_DEFAULT[group], min(total, FALLBACK_CAP)


def agreement_of(scores: dict[str, dict[str, float]]) -> str:
    if len(scores) < 2:
        return "single_source"
    tops = [_top_id(s) for s in scores.values()]
    if len(set(tops)) == 1:
        return "full"
    if len({GROUP_OF.get(t, "other") for t in tops}) == 1:
        return "partial"
    return "none"


def decide(scores: dict[str, dict[str, float]]) -> Decision:
    """scores: {source_name: {category_id: score}} for sources that returned ok."""
    scores = {k: v for k, v in scores.items() if v}
    if not scores:
        raise ValueError("no source scores")
    combined = calibrate(combine(scores))
    ranked = sorted(combined.items(), key=lambda kv: (-kv[1], kv[0]))
    top_id, top_score = ranked[0]
    agreement = agreement_of(scores)
    ok = top_score >= OK_MIN and (
        agreement in ("full", "partial")
        or (agreement == "single_source" and top_score >= SINGLE_OK_MIN)
    )
    hazards = [(c, s) for c, s in ranked if c in HAZARD_IDS and s >= HAZARD_MIN]
    hazard_id = hazards[0][0] if hazards else None
    fb = None if (ok or hazard_id) else group_fallback(ranked)
    if fb:
        default_id, conf = fb
        alts = [r for r in ranked[:2] if r[0] != default_id]
        return Decision(
            status="ok",
            category_id=default_id,
            confidence=round(conf, 4),
            alternatives=[(c, round(v, 4)) for c, v in alts],
            agreement=agreement,
            hazard=False,
            hazard_id=None,
            fallback=True,
        )
    if ok:
        alts = [r for r in ranked[1:] if r[1] >= ALT_MIN][:2]
    else:
        alts = ranked[:2]
        if hazard_id and hazard_id not in [a[0] for a in alts]:
            alts = [alts[0], (hazard_id, combined[hazard_id])]
    return Decision(
        status="ok" if ok else "uncertain",
        category_id=top_id if ok else None,
        confidence=round(top_score, 4),
        alternatives=[(c, round(s, 4)) for c, s in alts],
        agreement=agreement,
        hazard=hazard_id is not None,
        hazard_id=hazard_id,
    )

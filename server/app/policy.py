# File: server/app/policy.py
"""Decision policy v2 (A41, D-052). Flag POLICY_V2=false until the replay verdict is "pass".

Thresholds come from env (OK_MIN, SINGLE_OK_MIN, S_CLOUD) so they can be fitted on the replay set
and rolled back by unsetting them. Hazard rule is untouched: HAZARD_MIN stays in aggregator.py.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_S_CLOUD = 0.5
RESIDUAL = "general_residual"


def enabled() -> bool:
    return os.getenv("POLICY_V2", "false").strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Params:
    ok_min: float
    single_ok_min: float
    s_cloud: float


def _env_float(name: str, default: float) -> float:
    try:
        v = float(os.getenv(name, default))
    except ValueError:
        return default
    return v if 0.0 < v <= 1.0 else default


def params(ok_min: float, single_ok_min: float) -> Params:
    """Env overrides on top of the aggregator's baseline values."""
    return Params(_env_float("OK_MIN", ok_min), _env_float("SINGLE_OK_MIN", single_ok_min),
                  _env_float("S_CLOUD", DEFAULT_S_CLOUD))


def _top(cats: dict[str, float]) -> str:
    return max(cats.items(), key=lambda kv: (kv[1], kv[0]))[0]


def cloud_ok(scores: dict[str, dict[str, float]], strengths: dict[str, float] | None,
             s_cloud: float, hazard_ids: frozenset[str], group_of: dict[str, str]) -> str | None:
    """Strong cloud, weak local: the cloud's category when it may answer alone, else None.

    Needs evidence strengths (mapper v2). The cloud category must not be a hazard. A local
    disagreement is tolerated only when the local top is general_residual or in the same group;
    a disagreement across groups stays "uncertain".
    """
    if not strengths or "azure" not in scores or strengths.get("azure", 0.0) < s_cloud:
        return None
    cloud_top = _top(scores["azure"])
    if cloud_top in hazard_ids:
        return None
    local = scores.get("local_onnx")
    if local:
        lt = _top(local)
        if lt != cloud_top and lt != RESIDUAL and group_of.get(lt) != group_of.get(cloud_top):
            return None
    return cloud_top


def choose(results: list[dict], base: dict, max_uncertain: float = 40.0) -> dict | None:
    """Best grid row: max accuracy on ok, subject to uncertain <= 40%, hazard recall and
    confident-wrong (G-C: not up 3 points or more) against the baseline. Ties: fewer wrong, more ok."""
    def fine(r: dict) -> bool:
        return (r["uncertain"] <= max_uncertain and r["accuracy_on_ok"] is not None
                and (r["hazard_recall"] or 0) >= (base["hazard_recall"] or 0)
                and r["confident_wrong"] < base["confident_wrong"] + 3
                and r["top1"] >= base["top1"])
    ok = [r for r in results if fine(r)]
    return max(ok, key=lambda r: (r["accuracy_on_ok"], -r["confident_wrong"], r["ok_count"]), default=None)

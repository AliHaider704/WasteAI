# File: scripts/fit_temperature.py
"""Fit the aggregator TEMPERATURE by minimizing negative log-likelihood.

Input: JSON lines, one photo per line:
  {"scores": {"plastic_pet": 0.7, "plastic_unknown": 0.3}, "truth": "plastic_pet"}
where "scores" is aggregator.combine() output for that photo (before calibration).
Usage: python3 scripts/fit_temperature.py runs.jsonl [--min-photos 30]
Prints the best T and NLL at T=1.0 versus T=best. Does not edit any file.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

EPS = 1e-12


def load(path: Path) -> list[tuple[dict[str, float], str]]:
    rows = []
    for line in path.read_text("utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            rows.append(({k: float(v) for k, v in d["scores"].items()}, str(d["truth"])))
    return rows


def nll(rows: list[tuple[dict[str, float], str]], t: float) -> float:
    total = 0.0
    for scores, truth in rows:
        powered = {c: max(v, EPS) ** (1.0 / t) for c, v in scores.items()}
        z = sum(powered.values())
        total -= math.log(max(powered.get(truth, 0.0) / z, EPS))
    return total / len(rows)


def fit(rows: list[tuple[dict[str, float], str]]) -> tuple[float, float, float]:
    grid = [round(0.3 + 0.05 * i, 2) for i in range(55)]  # 0.30 .. 3.00
    best = min(grid, key=lambda t: nll(rows, t))
    return best, nll(rows, 1.0), nll(rows, best)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path)
    ap.add_argument("--min-photos", type=int, default=30)
    args = ap.parse_args()
    rows = load(args.path)
    if len(rows) < args.min_photos:
        print(f"FAIL: {len(rows)} photos, need at least {args.min_photos}", file=sys.stderr)
        return 1
    t, base, tuned = fit(rows)
    print(f"photos={len(rows)} best_T={t} nll_T1={base:.4f} nll_best={tuned:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

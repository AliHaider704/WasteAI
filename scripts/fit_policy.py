# File: scripts/fit_policy.py
"""A41: grid-search OK_MIN, SINGLE_OK_MIN, S_CLOUD on the replay set; write the report + hand-off.

  python3 scripts/fit_policy.py            (needs server/eval/runs/sources.jsonl, 100+ photos)
Uses mapper v2 (the cloud rule needs evidence strength). Objective: max accuracy on `ok`, subject to
uncertain <= 40%, hazard recall not lower, confident-wrong not up 3 points or more (G-C).
Appends a section to docs/FIELD_TEST_REPLAY.md and writes handoff/thresholds_summary.md.
Does not change any code default: adopt by setting the printed env values and POLICY_V2=true.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))
REPORT = ROOT / "docs" / "FIELD_TEST_REPLAY.md"
HANDOFF = ROOT / "docs" / "phases" / "accuracy" / "handoff" / "thresholds_summary.md"
GRID = {"OK_MIN": [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8],
        "SINGLE_OK_MIN": [0.7, 0.75, 0.8, 0.85, 0.9],
        "S_CLOUD": [0.3, 0.4, 0.5, 0.6]}
MIN_PHOTOS = 100


def load_replay():
    spec = importlib.util.spec_from_file_location("replay", ROOT / "scripts" / "replay.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_grid(rows, replay, mapper, agg, grid: dict | None = None) -> tuple[dict, list[dict]]:
    """-> (baseline metrics, one metrics row per grid point, each with its 'params')."""
    import os

    def with_env(env: dict[str, str | None]) -> None:
        for k, v in env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    grid = grid or GRID
    with_env({"POLICY_V2": None, "OK_MIN": None, "SINGLE_OK_MIN": None, "S_CLOUD": None})
    base = replay.metrics(rows, mapper, agg, True)
    out = []
    for combo in itertools.product(*grid.values()):
        env = {k: str(v) for k, v in zip(grid, combo, strict=True)}
        with_env({"POLICY_V2": "true", **env})
        out.append({**replay.metrics(rows, mapper, agg, True), "params": dict(zip(grid, combo, strict=True))})
    with_env({"POLICY_V2": None, "OK_MIN": None, "SINGLE_OK_MIN": None, "S_CLOUD": None})
    return base, out


def report_md(base: dict, best: dict | None, n: int) -> str:
    head = f"\n## A41 decision policy (sample: {n} photos, same photos in both rows)\n\n"
    if best is None:
        return head + "No grid point passed rule G-C. Defaults stay; `POLICY_V2` stays false.\n"
    rows = [("baseline (mapper v2, old policy)", base), (f"POLICY_V2 {best['params']}", best)]
    t = ["| Config | top1 | acc on ok | confident wrong | uncertain | hazard recall | fallback wrong |",
         "|---|---|---|---|---|---|---|"]
    t += [f"| {k} | {m['top1']} | {m['accuracy_on_ok']} | {m['confident_wrong']} | {m['uncertain']} | "
          f"{m['hazard_recall']} | {m['fallback_wrong_rate']} |" for k, m in rows]
    return head + "\n".join(t) + "\n\nVerdict: **pass** (G-C). Set the env values above and `POLICY_V2=true`.\n"


def summary_md(best: dict | None, n: int) -> str:
    if best is None:
        return ("<!-- File: docs/phases/accuracy/handoff/thresholds_summary.md -->\n"
                "# Thresholds summary\n\nNo change: the replay verdict was not a pass.\n")
    p = best["params"]
    return ("<!-- File: docs/phases/accuracy/handoff/thresholds_summary.md -->\n# Thresholds summary\n\n"
            f"Fitted on {n} photos. OK_MIN={p['OK_MIN']}, SINGLE_OK_MIN={p['SINGLE_OK_MIN']}, "
            f"S_CLOUD={p['S_CLOUD']}.\n\n"
            "- **High** (0.80 and up): sources agree or one is very strong. Show the answer plainly.\n"
            f"- **Medium** (from {p['OK_MIN']}): a good answer; show the alternatives.\n"
            "- **Not sure**: below that, sources disagree across groups, or evidence is weak. "
            "Hazard warnings still show whenever the hazard score is 0.35 or more.\n"
            f"- Expected share of \"Not sure\" on the test photos: {best['uncertain']}%.\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sources", type=Path)
    ap.add_argument("--force", action="store_true", help="allow fewer than 100 photos (do not adopt)")
    a = ap.parse_args(argv)
    replay = load_replay()
    from app import aggregator, mapper, policy
    rows = replay.load_rows(a.sources or replay.SOURCES)
    if len(rows) < MIN_PHOTOS and not a.force:
        print(f"FAIL: {len(rows)} photos; do not tune on fewer than {MIN_PHOTOS} (use --force to look)")
        return 1
    base, results = run_grid(rows, replay, mapper, aggregator)
    best = policy.choose(results, base)
    print("best:", best["params"] if best else "none passes G-C")
    if best:
        print({k: best[k] for k in ("top1", "accuracy_on_ok", "confident_wrong", "uncertain", "hazard_recall")})
    if len(rows) >= MIN_PHOTOS:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        with REPORT.open("a", encoding="utf-8") as fh:
            fh.write(report_md(base, best, len(rows)))
        HANDOFF.parent.mkdir(parents=True, exist_ok=True)
        HANDOFF.write_text(summary_md(best, len(rows)), "utf-8")
        print(f"report appended to {REPORT}; hand-off written to {HANDOFF}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

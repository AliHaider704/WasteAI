# File: scripts/replay.py
"""A36: replay saved source outputs through mapper + aggregator. Zero Azure calls.

  python3 scripts/replay.py --report                 baseline table
  python3 scripts/replay.py --report --out docs/FIELD_TEST_REPLAY.md
  python3 scripts/replay.py --mapper-module app.mapper --aggregator-module app.aggregator
  python3 scripts/replay.py --unmapped server/eval/runs/unmapped_tags.json
  python3 scripts/replay.py --fit-reliability          writes server/data/source_reliability.json
  python3 scripts/replay.py --table-a39                baseline / static cloud-first / reliability / +A37
  python3 scripts/replay.py --weight-mode reliability --mapper v2 --w-azure 0.6 --w-local 0.4
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))
SOURCES = ROOT / "server" / "eval" / "runs" / "sources.jsonl"
NAMES = {"local": "local_onnx", "azure": "azure"}


def load_rows(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text("utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def predict(row: dict, mapper, agg, v2: bool = False) -> dict:
    """One photo -> {status, top, ranked, hazard_id}. top is None when nothing matched."""
    usable, strengths = {}, {}
    for key, name in NAMES.items():
        pairs = [(t["label"], t["score"]) for t in (row.get(key) or [])]
        if v2 and pairs:
            from app import mapper_v2
            res = mapper_v2.map_labels_v2(pairs)
            scores = res.shares()
            strengths[name] = res.strength()
        else:
            scores = mapper.map_labels(pairs) if pairs else {}
        if scores:
            usable[name] = scores
    if not usable:
        return {"status": "uncertain", "top": None, "ranked": [], "hazard_id": None,
                "fallback": False}
    d = agg.decide(usable, strengths) if strengths else agg.decide(usable)
    ranked = [d.category_id] if d.category_id else []
    ranked += [c for c, _ in d.alternatives if c not in ranked]
    return {"status": d.status, "top": ranked[0] if ranked else None, "ranked": ranked,
            "hazard_id": d.hazard_id, "fallback": getattr(d, "fallback", False)}


def source_samples(rows: list[dict], mapper, agg) -> list[tuple[str, str, bool]]:
    """(source, group of its own top category, top was right) for reliability fitting."""
    out = []
    for r in rows:
        for key, name in NAMES.items():
            pairs = [(t["label"], t["score"]) for t in (r.get(key) or [])]
            scores = mapper.map_labels(pairs) if pairs else {}
            if scores:
                top = max(scores.items(), key=lambda kv: (kv[1], kv[0]))[0]
                out.append((name, agg.GROUP_OF.get(top, "other"), top == r["truth"]))
    return out


def metrics(rows: list[dict], mapper, agg, v2: bool = False) -> dict:
    n = len(rows)
    hits = Counter()
    conf: dict[str, Counter] = defaultdict(Counter)
    haz_total = haz_found = 0
    group_of = agg.GROUP_OF
    for r in rows:
        truth, p = r["truth"], predict(r, mapper, agg, v2)
        top = p["top"]
        conf[truth][top or "(none)"] += 1
        ok = p["status"] == "ok"
        hits["uncertain"] += not ok
        hits["top1"] += top == truth
        hits["top2"] += truth in p["ranked"][:2]
        hits["group"] += bool(top) and group_of.get(top) == group_of.get(truth)
        if p.get("fallback"):
            hits["fb"] += 1
            hits["fb_wrong"] += top != truth
        if ok:
            hits["ok"] += 1
            hits["ok_right"] += top == truth
            hits["conf_wrong"] += top != truth
        if truth in agg.HAZARD_IDS:
            haz_total += 1
            haz_found += top == truth or p["hazard_id"] == truth
    pct = lambda a, b: round(100.0 * a / b, 1) if b else None
    return {
        "photos": n, "top1": pct(hits["top1"], n), "top2_recall": pct(hits["top2"], n),
        "group_accuracy": pct(hits["group"], n), "uncertain": pct(hits["uncertain"], n),
        "ok_count": hits["ok"], "accuracy_on_ok": pct(hits["ok_right"], hits["ok"]),
        "confident_wrong": pct(hits["conf_wrong"], n),
        "fallback_wrong_rate": pct(hits["fb_wrong"], hits["fb"]), "fallback_n": hits["fb"],
        "hazard_recall": pct(haz_found, haz_total), "hazard_photos": haz_total,
        "confusion": {t: dict(c) for t, c in sorted(conf.items())},
    }


def unmapped(rows: list[dict], mapper) -> list[dict]:
    rules, cnt = mapper.load_rules(), Counter()
    for r in rows:
        for t in r.get("azure") or []:
            if not mapper._weights(t["label"], rules):
                cnt[t["label"].strip().lower()] += 1
    return [{"tag": k, "count": v} for k, v in cnt.most_common()]


def table(m: dict) -> str:
    keys = ["photos", "top1", "top2_recall", "group_accuracy", "accuracy_on_ok",
            "confident_wrong", "uncertain", "hazard_recall", "hazard_photos"]
    lines = ["| Metric | Value |", "|---|---|"]
    lines += [f"| {k} | {m[k]}{'' if k in ('photos', 'hazard_photos') else ' %'} |" for k in keys]
    return "\n".join(lines)


def confusion_md(m: dict) -> str:
    out = ["| Truth | Predicted (count) |", "|---|---|"]
    for t, c in m["confusion"].items():
        out.append(f"| {t} | " + ", ".join(f"{k}: {v}" for k, v in sorted(c.items(), key=lambda kv: -kv[1])) + " |")
    return "\n".join(out)


def report_md(m: dict, label: str) -> str:
    return (f"<!-- File: docs/FIELD_TEST_REPLAY.md -->\n# Field test replay ({label})\n\n"
            f"Generated by `scripts/replay.py` on {datetime.now(UTC).date()}. Source outputs captured once "
            f"by `scripts/capture_sources.py`; no Azure calls during replay. "
            f"Sample size: {m['photos']} photos.\n\n## Metrics\n{table(m)}\n\n"
            f"## Confusion (truth -> predicted)\n{confusion_md(m)}\n")


def set_env(env: dict[str, str]) -> None:
    """Apply a configuration: env values (None removes), then drop cached settings."""
    for k, v in env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    from app.config import get_settings
    get_settings.cache_clear()


CONFIGS = [
    ("baseline (local 0.6 / azure 0.4)", False, {"WEIGHT_MODE": None, "W_LOCAL": None, "W_AZURE": None}),
    ("static cloud-first (azure 0.6)", False, {"WEIGHT_MODE": None, "W_LOCAL": "0.4", "W_AZURE": "0.6"}),
    ("reliability", False, {"WEIGHT_MODE": "reliability", "W_LOCAL": "0.4", "W_AZURE": "0.6"}),
    ("reliability + A37 mapper v2", True, {"WEIGHT_MODE": "reliability", "W_LOCAL": "0.4", "W_AZURE": "0.6"}),
]


def table_a39(rows: list[dict], mapper, agg) -> str:
    out = ["| Config | top1 | acc on ok | confident wrong | uncertain | hazard recall | G-C |",
           "|---|---|---|---|---|---|---|"]
    base = None
    for label, v2, env in CONFIGS:
        set_env(env)
        m = metrics(rows, mapper, agg, v2)
        if base is None:
            base = m
        passed = (m["top1"] >= base["top1"] and m["confident_wrong"] < base["confident_wrong"] + 3
                  and (m["hazard_recall"] or 0) >= (base["hazard_recall"] or 0))
        out.append(f"| {label} | {m['top1']} | {m['accuracy_on_ok']} | {m['confident_wrong']} | "
                   f"{m['uncertain']} | {m['hazard_recall']} | {'pass' if passed else 'FAIL'} |")
    set_env({"WEIGHT_MODE": None, "W_LOCAL": None, "W_AZURE": None})
    return "\n".join(out) + f"\n\nSample size: {len(rows)} photos (same photos in every row)."


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sources", type=Path, default=SOURCES)
    ap.add_argument("--mapper-module", default="app.mapper")
    ap.add_argument("--aggregator-module", default="app.aggregator")
    ap.add_argument("--label", default="baseline: current mapper and aggregator")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--unmapped", type=Path)
    ap.add_argument("--mapper", choices=["v1", "v2"], default="v1")
    ap.add_argument("--weight-mode", choices=["static", "reliability"])
    ap.add_argument("--w-local")
    ap.add_argument("--w-azure")
    ap.add_argument("--fit-reliability", action="store_true")
    ap.add_argument("--reliability-file", type=Path)
    ap.add_argument("--table-a39", action="store_true")
    a = ap.parse_args(argv)
    if not a.sources.is_file():
        print(f"FAIL: {a.sources} missing (run scripts/capture_sources.py first)")
        return 1
    rows = load_rows(a.sources)
    mapper = importlib.import_module(a.mapper_module)
    agg = importlib.import_module(a.aggregator_module)
    if a.reliability_file:
        os.environ["RELIABILITY_PATH"] = str(a.reliability_file)
    if a.fit_reliability:
        from app import weighting
        out = a.reliability_file or weighting.reliability_path()
        table = weighting.fit(source_samples(rows, mapper, agg))
        out.write_text(json.dumps(table, indent=1) + "\n", "utf-8")
        print(f"reliability fitted on {len(rows)} photos -> {out}")
        print(json.dumps(table["sources"], indent=1))
        return 0
    if a.table_a39:
        print(table_a39(rows, mapper, agg))
        return 0
    set_env({"WEIGHT_MODE": a.weight_mode, "W_LOCAL": a.w_local, "W_AZURE": a.w_azure}
            if (a.weight_mode or a.w_local or a.w_azure) else {})
    m = metrics(rows, mapper, agg, a.mapper == "v2")
    if a.unmapped:
        a.unmapped.parent.mkdir(parents=True, exist_ok=True)
        a.unmapped.write_text(json.dumps({"tags": unmapped(rows, mapper)}, indent=1), "utf-8")
        print(f"unmapped tags written to {a.unmapped}")
    if a.report or not (a.out or a.unmapped):
        print(table(m))
        if m["photos"] < 100:
            print(f"WARNING: only {m['photos']} photos; G-A needs 100+")
    if a.out:
        a.out.write_text(report_md(m, a.label), "utf-8")
        print(f"report written to {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

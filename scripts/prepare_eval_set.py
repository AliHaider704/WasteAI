# File: scripts/prepare_eval_set.py
"""A36: copy owner photos into server/eval_photos/<category_id>/ using eval_labels.csv.

Usage: python3 scripts/prepare_eval_set.py --src <folder with the photos> [--csv PATH] [--dry-run]
CSV columns: filename,category_id (no photos in the CSV). Unknown ids are refused.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "docs/phases/accuracy/handoff/eval_labels.csv"
DEST = ROOT / "server" / "eval_photos"
MIN_TOTAL, MIN_PER_CAT = 100, 3


def known_ids() -> set[str]:
    data = json.loads((ROOT / "contract" / "categories.json").read_text("utf-8"))
    return {c["id"] for c in data["categories"]}


def read_rows(path: Path) -> list[tuple[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return [(r["filename"].strip(), r["category_id"].strip())
                for r in csv.DictReader(fh) if r.get("filename")]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", required=True, type=Path)
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if not a.csv.is_file():
        print(f"FAIL: no CSV at {a.csv}")
        return 1
    ids = known_ids()
    rows = read_rows(a.csv)
    bad = sorted({c for _, c in rows if c not in ids})
    if bad:
        print("FAIL: unknown category ids:", ", ".join(bad))
        return 1
    missing = [f for f, _ in rows if not (a.src / f).is_file()]
    if missing:
        print(f"FAIL: {len(missing)} photo(s) not found in {a.src}, first: {missing[:5]}")
        return 1
    counts: Counter[str] = Counter()
    for fname, cid in rows:
        counts[cid] += 1
        if not a.dry_run:
            out = DEST / cid
            out.mkdir(parents=True, exist_ok=True)
            shutil.copy2(a.src / fname, out / Path(fname).name)
    print(f"{'would copy' if a.dry_run else 'copied'} {len(rows)} photos")
    for cid in sorted(ids):
        n = counts.get(cid, 0)
        print(f"  {cid:22s} {n:3d}{'  <-- under ' + str(MIN_PER_CAT) if n < MIN_PER_CAT else ''}")
    ok = len(rows) >= MIN_TOTAL
    print(f"G-A: {'met' if ok else 'NOT met'} (need {MIN_TOTAL}+ photos, {MIN_PER_CAT}+ per category)")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())

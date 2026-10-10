# File: scripts/learn_tag_rules.py
"""A38: learn tag -> category weights from harvest.jsonl (public labelled photos only).

  python3 scripts/learn_tag_rules.py [--harvest PATH] [--translation-top 300]
Split 80/20 by photo (stable hash). A tag needs >= 3 training photos; association is smoothed
P(category | tag) / P(category) (lift); kept at lift >= 1.5; weight = log(lift)/log(10), capped 0..1.
Writes label_rules/learned/learned_NN.json (<= 400 labels each) and prints the counts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))
HARVEST = ROOT / "server" / "eval" / "runs" / "harvest.jsonl"
OUT = ROOT / "server" / "data" / "label_rules" / "learned"
HANDOFF = ROOT / "docs" / "phases" / "accuracy" / "handoff" / "azure_tags_for_translation.json"
MIN_PHOTOS, MIN_LIFT, LIFT_FULL, CHUNK, MAX_CATS = 3, 1.5, 10.0, 400, 3


def is_train(name: str) -> bool:
    return int(hashlib.sha1(name.encode()).hexdigest(), 16) % 10 < 8


def split(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    train = [r for r in rows if is_train(r["file"])]
    return train, [r for r in rows if not is_train(r["file"])]


def learn(rows: list[dict], min_photos: int = MIN_PHOTOS, min_lift: float = MIN_LIFT) -> dict:
    """-> {tag: {category: weight}}; each photo counts once per tag."""
    n = len(rows)
    cats = Counter(r["truth"] for r in rows)
    tag_n: Counter[str] = Counter()
    tag_c: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        for t in {x["label"].strip().lower() for x in r["tags"]}:
            tag_n[t] += 1
            tag_c[t][r["truth"]] += 1
    out: dict[str, dict[str, float]] = {}
    for tag, nt in tag_n.items():
        if nt < min_photos:
            continue
        scored = {}
        for c, ntc in tag_c[tag].items():
            p = (ntc + 1) / (nt + len(cats))
            lift = p / (cats[c] / n)
            if lift >= min_lift:
                scored[c] = round(min(1.0, math.log(lift) / math.log(LIFT_FULL)), 3)
        best = dict(sorted(scored.items(), key=lambda kv: -kv[1])[:MAX_CATS])
        if best:
            out[tag] = best
    return out


def predict(tags: list[dict], rules: dict) -> str | None:
    s: dict[str, float] = {}
    for t in tags:
        for c, w in rules.get(t["label"].strip().lower(), {}).items():
            s[c] = s.get(c, 0.0) + w * t["score"]
    return max(s, key=lambda c: (s[c], c)) if s else None


def holdout(rows: list[dict], rules: dict) -> dict:
    guessed = [(r["truth"], predict(r["tags"], rules)) for r in rows]
    hit = [(t, p) for t, p in guessed if p is not None]
    return {"photos": len(rows), "with_match": len(hit),
            "accuracy": round(100 * sum(t == p for t, p in hit) / len(hit), 1) if hit else None}


def write_rules(rules: dict, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("learned_??.json"):
        old.unlink()
    items = sorted(rules.items())
    for n, i in enumerate(range(0, len(items), CHUNK), 1):
        name = f"learned_{n:02d}.json"
        body = {"_path": f"server/data/label_rules/learned/{name}", "labels": dict(items[i:i + CHUNK])}
        (out / name).write_text(json.dumps(body, indent=1, ensure_ascii=False) + "\n", "utf-8")
    return len(items)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--harvest", type=Path, default=HARVEST)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--translation-top", type=int, default=300)
    ap.add_argument("--handoff", type=Path, default=HANDOFF)
    a = ap.parse_args(argv)
    if not a.harvest.is_file():
        print(f"FAIL: {a.harvest} missing (run scripts/harvest_tags.py)")
        return 1
    rows = [json.loads(x) for x in a.harvest.read_text("utf-8").splitlines() if x.strip()]
    train, test = split(rows)
    rules = learn(train)
    kept = write_rules(rules, a.out)
    from app import mapper
    existing = mapper._load(mapper.RULES_DIR) if mapper.RULES_DIR.is_dir() else {}
    seen = Counter(t["label"].strip().lower() for r in rows for t in r["tags"])
    mapped_before = sum(c for t, c in seen.items() if mapper._weights(t, existing))
    merged = {**existing, **{k: v for k, v in rules.items() if k not in existing}}
    mapped_after = sum(c for t, c in seen.items() if mapper._weights(t, merged))
    total = sum(seen.values()) or 1
    print(f"photos: {len(rows)} (train {len(train)}, hold-out {len(test)}); tags kept: {kept}")
    print(f"harvested tag occurrences mapped: before {100 * mapped_before / total:.1f}%, "
          f"after {100 * mapped_after / total:.1f}%")
    print("hold-out (learned rules only):", holdout(test, rules))
    left = Counter({t: c for t, c in seen.items() if not mapper._weights(t, merged)})
    a.handoff.parent.mkdir(parents=True, exist_ok=True)
    a.handoff.write_text(json.dumps(
        {"tags": [{"tag": t, "count": c} for t, c in left.most_common(a.translation_top)]},
        indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(f"translation hand-off: {min(len(left), a.translation_top)} unmapped tags -> {a.handoff}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

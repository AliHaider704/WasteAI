# File: scripts/build_seed_rules.py
"""A44 (dev machine only): word lists + WordNet -> server/data/label_rules/seed/*.json.

Inputs (you supply the lists, words only, no images or annotations; check licences first):
  --lists DIR   *.txt files, one class name per line (ImageNet-1k, Open Images, LVIS, COCO ...)
  server/data/seed_domain_terms.txt   hand-written terms: "term = category_id[:w], ..."
Needs nltk + the wordnet corpus for hypernym chains (pip install nltk; nltk.download("wordnet")).
Without WordNet it falls back to matching the last word of each term against the anchors.
Output: seed/<group>_NN.json (<= 400 labels each, weights 0.3-0.6), seed/review_queue.md
(the 200 least certain words), seed/stoplist_candidates.txt (people, animals, places, scenery).
A human reviews the queue before anything is committed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "server" / "data" / "label_rules" / "seed"
DOMAIN = ROOT / "server" / "data" / "seed_domain_terms.txt"
CHUNK, QUEUE = 400, 200
ANCHORS = {
    "plastic_unknown": ["bottle", "plastic", "container", "bag"],
    "metal_aluminum": ["can", "foil"], "metal_steel": ["tin", "cutlery"],
    "glass": ["jar", "glassware"], "carton_beverage": ["carton"],
    "paper": ["newspaper", "magazine", "paper"], "cardboard": ["box", "cardboard"],
    "textile": ["fabric", "clothing", "garment"], "battery": ["battery"],
    "organic_food": ["fruit", "vegetable", "food", "bread"], "organic_garden": ["leaf", "grass"],
    "wood": ["lumber", "timber", "plank"], "medical": ["medicine", "syringe"],
    "ewaste_small": ["telephone", "headphone", "camera"],
    "ewaste_large": ["computer", "refrigerator", "appliance"],
    "hazardous_chemical": ["paint", "pesticide", "solvent"], "construction": ["brick", "concrete"],
}
STOP_ROOTS = ["person.n.01", "animal.n.01", "location.n.01", "geological_formation.n.01", "plant.n.02"]
GROUPS = {"plastic": "plastics", "metal": "metals", "glass": "glass", "carton": "paper",
          "paper": "paper", "cardboard": "paper", "organic": "organic", "battery": "e-waste",
          "ewaste": "e-waste"}


def group_of(cid: str) -> str:
    return next((g for k, g in GROUPS.items() if cid.startswith(k)), "other")


def read_words(folder: Path) -> list[str]:
    words: set[str] = set()
    for f in sorted(folder.glob("*.txt")):
        for line in f.read_text("utf-8").splitlines():
            w = re.sub(r"[^a-z0-9 \-']", " ", line.split(",")[0].lower().replace("_", " ")).strip()
            if 2 < len(w) < 40:
                words.add(re.sub(r"\s+", " ", w))
    return sorted(words)


def read_domain(path: Path) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for line in path.read_text("utf-8").splitlines() if path.is_file() else []:
        if line.startswith("#") or "=" not in line:
            continue
        term, rhs = line.split("=", 1)
        slot = out.setdefault(term.strip().lower(), {})
        for part in rhs.split(","):
            cid, _, w = part.strip().partition(":")
            if cid:
                slot[cid] = float(w or 0.6)
    return out


def wordnet_scorer():
    try:
        from nltk.corpus import wordnet as wn
        wn.ensure_loaded()
    except (ImportError, LookupError, OSError):
        return None
    anchor_syn = {cid: {s for a in ws for s in wn.synsets(a, "n")[:2]}
                  for cid, ws in ANCHORS.items()}
    stop_syn = {wn.synset(n) for n in STOP_ROOTS}

    def score(word: str):
        """-> ("stop", None, 0) | ("cat", cid, distance) | None"""
        best = None
        for syn in wn.synsets(word.replace(" ", "_"), "n")[:3]:
            for path in syn.hypernym_paths():
                if stop_syn & set(path):
                    return ("stop", None, 0)
                for dist, node in enumerate(reversed(path)):
                    for cid, syns in anchor_syn.items():
                        if node in syns and (best is None or dist < best[2]):
                            best = ("cat", cid, dist)
        return best
    return score


def head_scorer():
    heads = {a: cid for cid, ws in ANCHORS.items() for a in ws}

    def score(word: str):
        cid = heads.get(word.split()[-1])
        return ("cat", cid, 1) if cid else None
    return score


def build(words: list[str], domain: dict, scorer) -> tuple[dict, list, list]:
    rules: dict[str, dict[str, float]] = {k: dict(v) for k, v in domain.items()}
    certain: dict[str, float] = {k: 1.0 for k in domain}
    stop: list[str] = []
    for w in words:
        if w in rules:
            continue
        res = scorer(w)
        if res is None:
            continue
        if res[0] == "stop":
            stop.append(w)
            continue
        _, cid, dist = res
        rules[w] = {cid: round(0.6 - 0.3 * min(dist, 6) / 6, 2)}
        certain[w] = 1.0 - min(dist, 6) / 6
    queue = sorted((k for k in rules if k not in domain), key=lambda k: certain[k])[:QUEUE]
    return rules, queue, stop


def write(rules: dict, queue: list, stop: list, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*_??.json"):
        old.unlink()
    by_group: dict[str, dict] = {}
    for label, w in rules.items():
        by_group.setdefault(group_of(max(w, key=w.get)), {})[label] = w
    for g, labels in by_group.items():
        items = sorted(labels.items())
        for n, i in enumerate(range(0, len(items), CHUNK), 1):
            name = f"{g.replace('-', '')}_{n:02d}.json"
            body = {"_path": f"server/data/label_rules/seed/{name}", "labels": dict(items[i:i + CHUNK])}
            (out / name).write_text(json.dumps(body, indent=1, ensure_ascii=False) + "\n", "utf-8")
    (out / "review_queue.md").write_text(
        "<!-- File: server/data/label_rules/seed/review_queue.md -->\n# Least certain seed words\n"
        "Accept, change or drop each (edit the seed file), then commit.\n\n"
        + "\n".join(f"- {k}: {rules[k]}" for k in queue) + "\n", "utf-8")
    (out / "stoplist_candidates.txt").write_text(
        "# File: server/data/label_rules/seed/stoplist_candidates.txt\n" + "\n".join(sorted(set(stop))) + "\n", "utf-8")
    return len(rules)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lists", type=Path, help="folder with *.txt word lists")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    words = read_words(a.lists) if a.lists else []
    scorer = wordnet_scorer()
    if scorer is None:
        print("WordNet not available: using head-word fallback")
        scorer = head_scorer()
    rules, queue, stop = build(words, read_domain(DOMAIN), scorer)
    print(f"{len(words)} words read, {write(rules, queue, stop, a.out)} seed labels written, "
          f"{len(stop)} stoplist candidates, {len(queue)} in review queue")
    return 0


if __name__ == "__main__":
    sys.exit(main())

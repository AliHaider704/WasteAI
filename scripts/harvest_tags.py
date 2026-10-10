# File: scripts/harvest_tags.py
"""A38: call Azure on PUBLIC labelled photos and save tag text only (no image bytes).

  python3 scripts/harvest_tags.py --dataset trashnet --photos ~/data/trashnet --limit 20   # probe
Photos layout: <photos>/<dataset class>/*.jpg ; class -> our category id via
server/eval/dataset_maps/<dataset>.json. Never use the owner's eval photos here (G-D).
Own counter (server/eval/runs/harvest_counter.json): max 1500 calls per month, stop at 3000 total.
Probe first: run --limit 20, read the usage in the Azure portal; if tags+objects counts as two
transactions, pass --per-call 2. Output: server/eval/runs/harvest.jsonl (resumable).
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))
RUNS = ROOT / "server" / "eval" / "runs"
MAPS = ROOT / "server" / "eval" / "dataset_maps"
API_VERSION = "2023-10-01"
MONTH_CAP, TOTAL_CAP = 1500, 3000
EXT = {".jpg", ".jpeg", ".png", ".webp"}


def load_counter(path: Path, now: str) -> dict:
    try:
        c = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        c = {}
    if c.get("month") != now:
        c = {"month": now, "month_count": 0, "total": int(c.get("total", 0))}
    return c


def budget_left(c: dict, month_cap: int = MONTH_CAP, total_cap: int = TOTAL_CAP) -> int:
    return max(0, min(month_cap - c["month_count"], total_cap - c["total"]))


def done_files(path: Path) -> set[str]:
    seen: set[str] = set()
    for line in path.read_text("utf-8").splitlines() if path.is_file() else []:
        try:
            seen.add(json.loads(line)["file"])
        except (ValueError, KeyError):
            continue
    return seen


def to_jpeg(path: Path, side: int = 1024) -> bytes:
    from PIL import Image
    img = Image.open(path).convert("RGB")
    img.thumbnail((side, side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)  # re-encoding drops EXIF
    return buf.getvalue()


def load_env(path: Path) -> None:
    for line in path.read_text("utf-8").splitlines() if path.is_file() else []:
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", required=True, help="name of server/eval/dataset_maps/<name>.json")
    ap.add_argument("--photos", required=True, type=Path)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=3.2, help="seconds between calls (20 per minute)")
    ap.add_argument("--per-call", type=int, default=1, help="transactions counted per call")
    ap.add_argument("--out", type=Path, default=RUNS / "harvest.jsonl")
    ap.add_argument("--counter", type=Path, default=RUNS / "harvest_counter.json")
    a = ap.parse_args(argv)

    import httpx
    from app.sources.vision_azure import top_labels

    load_env(ROOT / "server" / ".env")
    endpoint = os.getenv("AZURE_VISION_ENDPOINT", "").rstrip("/")
    key = os.getenv("AZURE_VISION_KEY", "")
    if not (endpoint and key):
        print("FAIL: AZURE_VISION_ENDPOINT / AZURE_VISION_KEY missing")
        return 1
    classes = json.loads((MAPS / f"{a.dataset}.json").read_text("utf-8"))["classes"]
    seen = done_files(a.out)
    todo = [(p, classes[p.parent.name]) for p in sorted(a.photos.glob("*/*"))
            if p.suffix.lower() in EXT and p.parent.name in classes
            and f"{a.dataset}/{p.parent.name}/{p.name}" not in seen]
    counter = load_counter(a.counter, time.strftime("%Y-%m", time.gmtime()))
    room = budget_left(counter) // max(1, a.per_call)
    todo = todo[: min(room, a.limit or len(todo))]
    print(f"{len(todo)} photos to harvest (budget left {budget_left(counter)}, used total {counter['total']})")
    RUNS.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=15) as client, a.out.open("a", encoding="utf-8") as fh:
        for i, (p, truth) in enumerate(todo, 1):
            name = f"{a.dataset}/{p.parent.name}/{p.name}"
            try:
                resp = client.post(
                    f"{endpoint}/computervision/imageanalysis:analyze",
                    params={"api-version": API_VERSION, "features": "tags,objects"},
                    content=to_jpeg(p),
                    headers={"Ocp-Apim-Subscription-Key": key, "Content-Type": "application/octet-stream"})
                counter["month_count"] += a.per_call
                counter["total"] += a.per_call
                a.counter.write_text(json.dumps(counter), "utf-8")
                resp.raise_for_status()
                tags = top_labels(resp.json(), limit=20)
            except (httpx.HTTPError, ValueError, OSError) as exc:
                print(f"[{i}] {name}: {type(exc).__name__}")
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (401, 403, 429):
                    print("stopping:", exc.response.status_code)
                    break
                continue
            fh.write(json.dumps({"file": name, "truth": truth, "tags": tags}, ensure_ascii=False) + "\n")
            fh.flush()
            print(f"[{i}/{len(todo)}] {name} {len(tags)} tags")
            time.sleep(a.delay)
    print(f"counter: month {counter['month_count']}/{MONTH_CAP}, total {counter['total']}/{TOTAL_CAP}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

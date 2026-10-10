# File: scripts/capture_sources.py
"""A36: call local + Azure ONCE per owner photo, save raw tag output (no image bytes).

Run on the host with its own key:  cd server && python3 ../scripts/capture_sources.py
Output: server/eval/runs/sources.jsonl, one row per photo:
  {"file","truth","local":[{label,score}]|null,"azure":[{label,score}]|null}
Resumable: photos already in the file are skipped. Azure calls count against the app quota.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))
PHOTOS = ROOT / "server" / "eval_photos"
OUT = ROOT / "server" / "eval" / "runs" / "sources.jsonl"
EXT = {".jpg", ".jpeg", ".png", ".webp"}


def load_env(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text("utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def photos(root: Path) -> list[tuple[Path, str]]:
    return sorted((p, p.parent.name) for p in root.glob("*/*") if p.suffix.lower() in EXT)


def norm(top) -> list[dict]:
    out = []
    for t in top or []:
        lb, sc = (t[0], t[1]) if isinstance(t, tuple | list) else (t["label"], t["score"])
        out.append({"label": str(lb), "score": round(float(sc), 4)})
    return out


def done_files(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    seen = set()
    for line in path.read_text("utf-8").splitlines():
        try:
            seen.add(json.loads(line)["file"])
        except (ValueError, KeyError):
            continue
    return seen


async def one(src, arg) -> list[dict] | None:
    try:
        res = await src.classify(arg)
    except Exception:
        return None
    return norm(res.top) if res.ok else None


async def run(a) -> int:
    load_env(ROOT / "server" / ".env")
    from app import imaging
    from app.sources.vision_azure import VisionAzure
    from app.sources.vision_local import VisionLocal

    local = VisionLocal.from_env()
    local.load()
    azure = VisionAzure.from_env()
    if not azure.enabled and not a.local_only:
        print("FAIL: Azure key missing (use --local-only to skip Azure)")
        return 1
    items = photos(a.photos)
    seen = done_files(a.out)
    todo = [(p, t) for p, t in items if f"{t}/{p.name}" not in seen]
    print(f"{len(items)} photos, {len(seen)} done, {len(todo)} to do")
    if a.limit:
        todo = todo[: a.limit]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("a", encoding="utf-8") as fh:
        for i, (p, truth) in enumerate(todo, 1):
            data = p.read_bytes()
            try:
                prepared = imaging.prepare(data)
            except Exception:
                print("skip (bad image):", p.name)
                continue
            loc = await one(local, prepared)
            az = None if a.local_only else await one(azure, data)
            prepared.close()
            row = {"file": f"{truth}/{p.name}", "truth": truth, "local": loc, "azure": az}
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            print(f"[{i}/{len(todo)}] {row['file']} local={'ok' if loc else 'fail'} "
                  f"azure={'ok' if az else 'fail'}")
            if not a.local_only:
                time.sleep(a.delay)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--photos", type=Path, default=PHOTOS)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--delay", type=float, default=3.5, help="seconds between Azure calls (F0: 20/min)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--local-only", action="store_true")
    return asyncio.run(run(ap.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())

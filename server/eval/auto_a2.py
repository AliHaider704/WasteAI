# File: server/eval/auto_a2.py
"""Phase A2, fully automatic. Run from anywhere:  python server/eval/auto_a2.py

1. Installs missing packages (onnxruntime, numpy, Pillow, psutil).
2. Downloads test photos from Wikimedia Commons into server/eval_photos/<category_id>/
   (skipped if that folder already has photos, so your own photos are never overwritten).
3. Searches Hugging Face for ONNX waste classifiers, downloads them, reads id2label,
   maps labels to our category ids by keywords.
4. Evaluates every usable candidate (top-1, top-3, p50 latency, RSS, size, license).
5. Picks the winner (permissive license only), writes server/data/model_labels.json,
   server/.env.example (MODEL_URL, MODEL_SHA256), server/eval/results.md,
   and prints a DECISIONS row.
NOTE: web photos are a smoke evaluation, not the official one on the owner's photos (D-009).
"""
import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


def ensure(pkgs: dict) -> None:
    for mod, pip_name in pkgs.items():
        try:
            __import__(mod)
        except ImportError:
            for extra in ([], ["--break-system-packages"]):
                if subprocess.call([sys.executable, "-m", "pip", "install", "-q", pip_name, *extra]) == 0:
                    break


ensure({"onnxruntime": "onnxruntime", "numpy": "numpy", "PIL": "Pillow", "psutil": "psutil"})
import numpy as np  # noqa: E402
import onnxruntime as ort  # noqa: E402
import psutil  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "server"
PHOTOS = SERVER / "eval_photos"
CACHE = SERVER / "eval" / "_cache"
UA = {"User-Agent": "WasteAI-eval/1.0 (A2 model evaluation script)"}
PER_CAT = 8
MAX_MODELS = 10
MAX_MB = 150
PERMISSIVE = ("apache-2.0", "mit", "bsd", "cc-by-4.0", "cc0-1.0", "unlicense")

SEARCH = {
    "paper": "paper sheets", "cardboard": "cardboard box", "glass": "glass bottle",
    "metal_aluminum": "aluminum can", "metal_steel": "steel tin can",
    "plastic_unknown": "plastic bottle", "organic_food": "food scraps",
    "battery": "alkaline batteries", "textile": "clothes pile",
    "general_residual": "trash garbage", "ewaste_small": "old mobile phone",
    "carton_beverage": "juice carton",
}
KEYWORDS = [  # label keyword -> our category ids
    ("cardboard", ["cardboard"]), ("carton", ["carton_beverage"]), ("paper", ["paper"]),
    ("glass", ["glass"]), ("battery", ["battery"]), ("metal", ["metal_aluminum", "metal_steel", "metal_other"]),
    ("can", ["metal_aluminum", "metal_steel"]), ("alumin", ["metal_aluminum"]),
    ("plastic", ["plastic_unknown", "plastic_pet", "plastic_hdpe", "plastic_pvc", "plastic_ldpe",
                 "plastic_pp", "plastic_ps", "plastic_other"]),
    ("styrofoam", ["plastic_ps"]), ("bio", ["organic_food", "organic_garden"]),
    ("organic", ["organic_food", "organic_garden"]), ("food", ["organic_food"]),
    ("compost", ["organic_food", "organic_garden"]), ("cloth", ["textile"]), ("textile", ["textile"]),
    ("shoe", ["textile"]), ("trash", ["general_residual"]), ("residual", ["general_residual"]),
    ("general", ["general_residual"]), ("electronic", ["ewaste_small", "ewaste_large"]),
    ("e-waste", ["ewaste_small", "ewaste_large"]), ("wood", ["wood"]),
]


def http(url: str, tries: int = 3) -> bytes:
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except Exception:
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"download failed: {url}")


def jget(url: str):
    return json.loads(http(url))


# ---------------------------------------------------------------- photos
def fetch_photos() -> None:
    PHOTOS.mkdir(parents=True, exist_ok=True)
    for cat, term in SEARCH.items():
        d = PHOTOS / cat
        if d.is_dir() and any(d.iterdir()):
            continue
        d.mkdir(exist_ok=True)
        q = urllib.parse.urlencode({
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": f"{term} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": 25,
            "prop": "imageinfo", "iiprop": "url|mime", "iiurlwidth": 640})
        try:
            pages = jget("https://commons.wikimedia.org/w/api.php?" + q)["query"]["pages"].values()
        except Exception as e:
            print(f"  photos {cat}: search failed ({e})")
            continue
        n = 0
        for p in pages:
            info = (p.get("imageinfo") or [{}])[0]
            if info.get("mime") != "image/jpeg" or n >= PER_CAT:
                continue
            try:
                (d / f"{n:02d}.jpg").write_bytes(http(info.get("thumburl") or info["url"]))
                n += 1
                time.sleep(0.4)
            except Exception:
                pass
        print(f"  photos {cat}: {n}")


def load_photos():
    items = []
    for d in sorted(PHOTOS.iterdir()):
        if d.is_dir() and d.name in SEARCH:
            for f in sorted(d.iterdir()):
                if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                    try:
                        with Image.open(f) as im:
                            items.append((d.name, im.convert("RGB").copy()))
                    except Exception:
                        pass
    return items


# ---------------------------------------------------------------- models
def map_label(label: str) -> list:
    low = label.lower()
    for kw, ids in KEYWORDS:
        if kw in low:
            return ids
    return []


def find_candidates() -> list:
    seen, out = set(), []
    for term in ("garbage", "waste", "trash", "recycl"):
        url = f"https://huggingface.co/api/models?search={term}&filter=onnx&limit=30&full=true"
        try:
            models = jget(url)
        except Exception:
            continue
        for m in models:
            mid = m.get("id") or m.get("modelId")
            files = [s["rfilename"] for s in m.get("siblings", [])]
            onnx = [f for f in files if f.endswith(".onnx")]
            if mid in seen or not onnx or "config.json" not in files:
                continue
            seen.add(mid)
            lic = next((t.split(":", 1)[1] for t in m.get("tags", []) if t.startswith("license:")), "unknown")
            pref = [f for f in onnx if f.split("/")[-1] == "model.onnx"] or [f for f in onnx if "quant" not in f] or onnx
            out.append({"id": mid, "file": pref[0], "license": lic.lower()})
    return out[:MAX_MODELS]


def download(url: str, dest: Path) -> bool:
    if dest.exists():
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r, dest.open("wb") as f:
            total = 0
            while chunk := r.read(1 << 20):
                total += len(chunk)
                if total > MAX_MB * 1e6:
                    raise RuntimeError("too large")
                f.write(chunk)
        return True
    except Exception:
        dest.unlink(missing_ok=True)
        return False


def prep_cfg(base: str, cfg: dict):
    mean, std, size = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225], None
    try:
        pc = jget(f"{base}/preprocessor_config.json")
        mean, std = pc.get("image_mean", mean), pc.get("image_std", std)
        s = pc.get("size")
        size = s if isinstance(s, int) else (s or {}).get("height") or (s or {}).get("shortest_edge")
    except Exception:
        pass
    return mean, std, size


def preprocess(im, size, mean, std, layout, mode):
    if mode == "crop":
        w, h = im.size
        k = size / 0.875 / min(w, h)
        im = im.resize((max(size, round(w * k)), max(size, round(h * k))), Image.BILINEAR)
        w, h = im.size
        l, t = (w - size) // 2, (h - size) // 2
        im = im.crop((l, t, l + size, t + size))
    else:
        im = im.resize((size, size), Image.BILINEAR)
    a = (np.asarray(im, dtype=np.float32) / 255.0 - np.array(mean, np.float32)) / np.array(std, np.float32)
    a = a.transpose(2, 0, 1) if layout == "nchw" else a
    return a[None].astype(np.float32)


def softmax(x):
    e = np.exp(x - x.max())
    return e / e.sum()


def evaluate(path: Path, labels: list, size_hint, mean, std, photos) -> dict | None:
    proc = psutil.Process()
    before = proc.memory_info().rss
    so = ort.SessionOptions()
    so.intra_op_num_threads = 1
    try:
        sess = ort.InferenceSession(str(path), so, providers=["CPUExecutionProvider"])
    except Exception:
        return None
    rss = (proc.memory_info().rss - before) / 1e6
    inp = sess.get_inputs()[0]
    shp = inp.shape
    if len(shp) != 4:
        return None
    layout = "nchw" if shp[1] == 3 else "nhwc" if shp[3] == 3 else None
    if layout is None:
        return None
    dim = shp[2] if layout == "nchw" else shp[1]
    size = dim if isinstance(dim, int) else (size_hint or 224)
    best = None
    for mode in ("squash", "crop"):
        ok1 = ok3 = n = 0
        times = []
        try:
            for cat, im in photos:
                x = preprocess(im, size, mean, std, layout, mode)
                t0 = time.perf_counter()
                out = sess.run(None, {inp.name: x})[0].reshape(-1).astype(np.float64)
                times.append((time.perf_counter() - t0) * 1000)
                if len(out) != len(labels):
                    return None
                p = softmax(out) if abs(out.sum() - 1) > 1e-3 or out.min() < 0 else out
                top = np.argsort(-p)[:3]
                hit = [cat in map_label(labels[i]) for i in top]
                ok1 += hit[0]
                ok3 += any(hit)
                n += 1
        except Exception:
            return None
        r = {"top1": ok1 / n, "top3": ok3 / n, "p50": float(np.median(times)), "rss": rss,
             "size": size, "norm": "imagenet" if mean == [0.485, 0.456, 0.406] else "custom",
             "mode": mode, "n": n, "mean": mean, "std": std, "layout": layout}
        if best is None or r["top1"] > best["top1"]:
            best = r
    return best


# ---------------------------------------------------------------- main
def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    print("1/4 photos")
    fetch_photos()
    photos = load_photos()
    if len(photos) < 20:
        print("Too few photos downloaded (check internet). Stop.")
        return 1
    print(f"   {len(photos)} photos")
    print("2/4 candidates")
    results = []
    for c in find_candidates():
        base = f"https://huggingface.co/{c['id']}/resolve/main"
        slug = re.sub(r"[^a-z0-9]+", "_", c["id"].lower())
        try:
            cfg = jget(f"{base}/config.json")
            id2 = cfg["id2label"]
            labels = [id2[str(i)] for i in range(len(id2))]
        except Exception:
            print(f"   skip {c['id']}: no id2label")
            continue
        if sum(bool(map_label(x)) for x in labels) < 3:
            print(f"   skip {c['id']}: labels not mappable")
            continue
        url = f"{base}/{c['file']}"
        path = CACHE / f"{slug}.onnx"
        print(f"   download {c['id']} ({c['license']})")
        if not download(url, path):
            print("   skip: download failed or too large")
            continue
        mean, std, size = prep_cfg(base, cfg)
        r = evaluate(path, labels, size, mean, std, photos)
        if not r:
            print("   skip: cannot run")
            continue
        r.update(id=c["id"], slug=slug, url=url, license=c["license"], labels=labels,
                 path=path, mb=path.stat().st_size / 1e6)
        results.append(r)
        print(f"   top1 {r['top1']:.1%} top3 {r['top3']:.1%} p50 {r['p50']:.0f} ms rss {r['rss']:.0f} MB")
    print("3/4 selection")
    if not results:
        print("No usable candidate found.")
        return 1
    results.sort(key=lambda r: (-r["top1"], r["p50"]))
    ok = [r for r in results if any(r["license"].startswith(p) for p in PERMISSIVE)
          and r["rss"] <= 200 and r["p50"] <= 600]
    win = ok[0] if ok else None
    rows = "\n".join(
        f"| {r['id']} | {r['n']} | {r['top1']:.1%} | {r['top3']:.1%} | {r['p50']:.0f} | {r['rss']:.0f} "
        f"| {r['mb']:.1f} | {r['license']} | verify | {'CHOSEN' if r is win else '-'} |" for r in results)
    if win:
        chosen = (f"{win['id']}. Model URL: {win['url']}. SHA256: {sha256(win['path'])}. "
                  f"Web photos (Wikimedia Commons), smoke evaluation: repeat on the owner's photos.")
    else:
        chosen = "NONE: no candidate has a permissive license and fits the speed/RAM limits. Nothing activated."
    (SERVER / "eval" / "results.md").write_text(
        "<!-- File: server/eval/results.md -->\nStatus: **RUN** by auto_a2.py on web photos "
        "(Wikimedia Commons), not on owner photos.\n\n## Comparison (1 thread, CPU)\n"
        "| Candidate | Photos | Top-1 | Top-3 | p50 ms | RSS MB | ONNX MB | Model license | Dataset license | Verdict |\n"
        f"|---|---|---|---|---|---|---|---|---|---|\n{rows}\n\n## Chosen model\n{chosen}\n", encoding="utf-8")
    if not win:
        print(chosen)
        return 0
    print("4/4 activate", win["id"])
    lp = SERVER / "data" / "model_labels.json"
    data = json.loads(lp.read_text(encoding="utf-8"))
    data.setdefault("label_sets", {})[win["slug"]] = {
        "labels": win["labels"], "map": {x: map_label(x) for x in win["labels"]},
        "size": win["size"], "norm": win["norm"], "mean": win["mean"], "std": win["std"],
        "layout": win["layout"], "resize": win["mode"]}
    data["active"] = win["slug"]
    lp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ep = SERVER / ".env.example"
    env = ep.read_text(encoding="utf-8")
    for k, v in (("MODEL_URL", win["url"]), ("MODEL_SHA256", sha256(win["path"]))):
        env = re.sub(rf"^{k}=.*$", f"{k}={v}", env, flags=re.M)
    ep.write_text(env, encoding="utf-8")
    print("\nDECISIONS row (append yourself):")
    print(f"| D-0XX | {time.strftime('%Y-%m-%d')} | [Ali] | accepted | Close D-011: model {win['id']}, "
          f"license {win['license']}, top-1 {win['top1']:.1%} on web photos (smoke test), "
          f"p50 {win['p50']:.0f} ms, RSS {win['rss']:.0f} MB. Repeat on owner photos. | A2 evaluation (D-009) |")
    return 0


if __name__ == "__main__":
    sys.exit(main())

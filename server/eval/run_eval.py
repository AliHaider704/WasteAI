# server/eval/run_eval.py
"""Evaluate one ONNX candidate on our own photos. Dev PC only (onnxruntime, numpy, Pillow).

Example:
  python run_eval.py --name mobilenet_v2_garbage --model m.onnx --label-set garbage12 \
      --size 224 --norm imagenet --layout nchw
Photos: eval_photos_prepared/<category_id>/*.jpg (folder name = true category id).
Prints a markdown block and writes eval/runs/<name>.md.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

GROUPS = {
    "plastics": "plastic_pet plastic_hdpe plastic_pvc plastic_ldpe plastic_pp plastic_ps plastic_other plastic_unknown",
    "paper": "paper cardboard carton_beverage",
    "glass": "glass",
    "metals": "metal_aluminum metal_steel metal_other",
    "organic": "organic_food organic_garden",
    "e-waste": "ewaste_small ewaste_large battery",
    "other": "textile hazardous_chemical medical wood construction general_residual",
}
GROUP_OF = {c: g for g, ids in GROUPS.items() for c in ids.split()}
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def rss_mb() -> float:
    try:
        import psutil

        return psutil.Process().memory_info().rss / 1048576
    except ImportError:
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # KB on Linux


def preprocess(path: Path, size: int, norm: str, layout: str, resize: str) -> np.ndarray:
    with Image.open(path) as im:
        im = im.convert("RGB")
        if resize == "crop":
            w, h = im.size
            s = size / min(w, h)
            im = im.resize((max(size, round(w * s)), max(size, round(h * s))), Image.BICUBIC)
            w, h = im.size
            left, top = (w - size) // 2, (h - size) // 2
            im = im.crop((left, top, left + size, top + size))
        else:
            im = im.resize((size, size), Image.BICUBIC)
        x = np.asarray(im, dtype=np.float32)
    if norm == "imagenet":
        x = (x / 255.0 - MEAN) / STD
    elif norm == "unit":
        x = x / 255.0
    if layout == "nchw":
        x = x.transpose(2, 0, 1)
    return x[None].astype(np.float32)


def softmax(v: np.ndarray) -> np.ndarray:
    e = np.exp(v - v.max())
    return e / e.sum()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--label-set", required=True, help="key in model_labels.json")
    ap.add_argument("--labels", default="../data/model_labels.json")
    ap.add_argument("--photos", default="eval_photos_prepared")
    ap.add_argument("--size", type=int, default=224)
    ap.add_argument("--norm", choices=["imagenet", "unit", "raw"], default="imagenet")
    ap.add_argument("--layout", choices=["nchw", "nhwc"], default="nchw")
    ap.add_argument("--resize", choices=["squash", "crop"], default="squash")
    ap.add_argument("--out-dir", default="runs")
    a = ap.parse_args()

    cfg = json.loads(Path(a.labels).read_text(encoding="utf-8"))["label_sets"][a.label_set]
    labels, lmap = cfg["labels"], cfg["map"]

    so = ort.SessionOptions()
    so.intra_op_num_threads = 1  # same as production
    t0 = time.perf_counter()
    sess = ort.InferenceSession(a.model, so, providers=["CPUExecutionProvider"])
    load_s = time.perf_counter() - t0
    inp = sess.get_inputs()[0].name
    size_mb = Path(a.model).stat().st_size / 1048576

    files = []
    for cat in sorted(p for p in Path(a.photos).iterdir() if p.is_dir()):
        if cat.name not in GROUP_OF:
            print(f"warning: folder {cat.name} is not a known category id")
        files += [(cat.name, f) for f in sorted(cat.iterdir()) if f.suffix.lower() in EXTS]
    if not files:
        raise SystemExit("no photos found")

    sess.run(None, {inp: preprocess(files[0][1], a.size, a.norm, a.layout, a.resize)})  # warmup
    rss_after = rss_mb()

    n = t1 = t3 = g1 = 0
    lat = []
    per = {}
    unmapped = set()
    for true, f in files:
        x = preprocess(f, a.size, a.norm, a.layout, a.resize)
        s = time.perf_counter()
        out = sess.run(None, {inp: x})[0].reshape(-1)
        lat.append((time.perf_counter() - s) * 1000)
        p = out if abs(out.sum() - 1) < 1e-3 and out.min() >= 0 else softmax(out)
        top = np.argsort(-p)[:3]
        names = [labels[i] if i < len(labels) else f"#{i}" for i in top]
        cats = [set(lmap.get(nm, [])) for nm in names]
        unmapped |= {nm for nm, c in zip(names, cats) if not c}
        ok1 = true in cats[0]
        ok3 = any(true in c for c in cats)
        gok = GROUP_OF.get(true) in {GROUP_OF[c] for c in cats[0] if c in GROUP_OF}
        n += 1
        t1 += ok1
        t3 += ok3
        g1 += gok
        d = per.setdefault(true, [0, 0, 0])
        d[0] += 1
        d[1] += ok1
        d[2] += ok3

    lat_a = np.array(lat)
    lines = [
        f"## {a.name}",
        "",
        f"| photos | top-1 | top-3 | top-1 group | p50 ms | p95 ms | RSS MB | ONNX MB | load s |",
        "|---|---|---|---|---|---|---|---|---|",
        f"| {n} | {t1/n:.1%} | {t3/n:.1%} | {g1/n:.1%} | {np.percentile(lat_a, 50):.0f} | "
        f"{np.percentile(lat_a, 95):.0f} | {rss_after:.0f} (peak {rss_mb():.0f}) | {size_mb:.1f} | {load_s:.1f} |",
        "",
        "| category | n | top-1 | top-3 |",
        "|---|---|---|---|",
    ]
    lines += [f"| {c} | {d[0]} | {d[1]/d[0]:.0%} | {d[2]/d[0]:.0%} |" for c, d in sorted(per.items())]
    if unmapped:
        lines += ["", f"Labels without a category map (fix `model_labels.json`): {sorted(unmapped)}"]
    text = "\n".join(lines) + "\n"
    print(text)
    out = Path(a.out_dir)
    out.mkdir(exist_ok=True)
    (out / f"{a.name}.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()

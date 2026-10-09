# File: scripts/check_budget.py
"""Size budgets (stdlib only). Eager = index.html + linked css + js reachable by static import from the
page script. Lazy = each js/features/<slug>.js with its css, data and two i18n files.
Usage: python3 scripts/check_budget.py [--measure]   (--measure prints numbers and always exits 0)."""
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FE = ROOT / "frontend"
BUDGET = ROOT / "scripts" / "budget.json"
IMPORT = re.compile(r'(?:^|\n)\s*(?:import|export)\s[^;\n]*?from\s*["\'](\.[^"\']+)["\']|(?:^|\n)\s*import\s*["\'](\.[^"\']+)["\']')


def sizes(paths):
    raw = gz = 0
    for p in paths:
        data = p.read_bytes()
        raw += len(data)
        gz += len(gzip.compress(data, 9))
    return raw, gz


def eager_files():
    html = FE / "index.html"
    text = html.read_text(encoding="utf-8")
    files = {html}
    for href in re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"', text):
        if not href.startswith(("http", "//")) and (FE / href).exists():
            files.add(FE / href)
    todo = [FE / s for s in re.findall(r'<script[^>]+src="([^"]+)"', text) if (FE / s).exists()]
    while todo:
        f = todo.pop()
        if f in files:
            continue
        files.add(f)
        for m in IMPORT.finditer(f.read_text(encoding="utf-8")):
            target = (f.parent / (m.group(1) or m.group(2))).resolve()
            if target.exists():
                todo.append(target)
    return sorted(files)


def lazy_features():
    out = {}
    fdir = FE / "js" / "features"
    if not fdir.is_dir():
        return out
    infra = {"registry", "store", "base"}
    for js in sorted(fdir.glob("*.js")):
        slug = js.stem
        if slug in infra or slug.startswith("_"):
            continue
        extra = [FE / "css" / "features" / f"{slug}.css", FE / "data" / f"{slug}.json",
                 FE / "i18n" / "features" / f"{slug}.ar.json", FE / "i18n" / "features" / f"{slug}.en.json"]
        out[slug] = [js] + [p for p in extra if p.exists()]
    return out


def main(argv):
    measure = "--measure" in argv
    eager_raw, eager_gz = sizes(eager_files())
    print(f"eager: {eager_raw} B raw, {eager_gz} B gzip ({len(eager_files())} files)")
    lazy = {s: sizes(p) for s, p in lazy_features().items()}
    for s, (r, g) in lazy.items():
        print(f"lazy {s}: {r} B raw, {g} B gzip")
    if measure:
        return 0
    if not BUDGET.exists():
        print("FAIL: scripts/budget.json missing")
        return 1
    b = json.loads(BUDGET.read_text(encoding="utf-8"))
    bad = 0
    if eager_gz > b["eager_gzip_max"] or eager_raw > b["eager_raw_max"]:
        print(f"FAIL: eager over budget (gzip max {b['eager_gzip_max']}, raw max {b['eager_raw_max']})")
        bad = 1
    for s, (r, g) in lazy.items():
        if g > b["lazy_gzip_max"] or r > b["lazy_raw_max"]:
            print(f"FAIL: lazy feature {s} over budget (gzip max {b['lazy_gzip_max']}, raw max {b['lazy_raw_max']})")
            bad = 1
    if not bad:
        print("OK: budgets respected")
    return bad


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

# File: content/tools/check_feature_data.py
"""Checks frontend/data/*.json (except features.json), feature modules and namespace files (M31)."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend"
LANGS = ("ar", "en")
HAZARD = re.compile(r"\b(battery|hazardous_chemical|medical|ewaste_\w+)\b")
errors = []


def err(msg):
    errors.append(msg)


def load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        err(f"{path.relative_to(ROOT)}: cannot read ({exc})")
        return None


def check_entry(rel, i, e):
    where = f"{rel}: entry {i}"
    if not isinstance(e, dict):
        return err(f"{where}: not an object")
    for key in ("id", "ar", "en", "source"):
        if not e.get(key):
            err(f"{where}: missing '{key}'")
    src = e.get("source")
    if isinstance(src, dict):
        kind = src.get("kind")
        if kind not in ("internal", "external"):
            err(f"{where}: source.kind must be internal or external")
        if kind == "external":
            for key in ("url", "accessed"):
                if not src.get(key):
                    err(f"{where}: external source needs '{key}'")
    elif src:
        err(f"{where}: source must be an object")


def check_data(flags):
    playful = {s for s, f in flags.items() if f.get("playful")}
    for path in sorted((FE / "data").glob("*.json")):
        if path.name == "features.json":
            continue
        rel = path.relative_to(ROOT).as_posix()
        data = load(path)
        if not isinstance(data, dict):
            continue
        if data.get("_path") != rel:
            err(f"{rel}: _path must be '{rel}'")
        for i, e in enumerate(data.get("entries", [])):
            check_entry(rel, i, e)
        if path.stem in playful and HAZARD.search(json.dumps(data.get("entries", []))):
            err(f"{rel}: a playful file mentions a hazard category")


def check_modules(flags):
    for slug, f in flags.items():
        if f.get("enabled") is True:
            module = FE / "js" / "features" / f"{f.get('module', slug)}.js"
            if not module.is_file():
                err(f"features.json: '{slug}' is enabled but {module.relative_to(ROOT)} is missing")


def check_namespaces(flags):
    folder = FE / "i18n" / "features"
    slugs = {p.name.rsplit(".", 2)[0] for p in folder.glob("*.json")}
    slugs |= {s for s, f in flags.items() if f.get("enabled") is True}
    for slug in sorted(slugs):
        keys = {}
        for lang in LANGS:
            path = folder / f"{slug}.{lang}.json"
            if not path.is_file():
                err(f"i18n/features/{slug}.{lang}.json is missing")
                continue
            data = load(path) or {}
            keys[lang] = {k for k in data if not k.startswith("_")}
            for k in keys[lang]:
                if not k.startswith(f"f.{slug}."):
                    err(f"{path.name}: key '{k}' must start with f.{slug}.")
        if len(keys) == 2 and keys["ar"] != keys["en"]:
            diff = sorted(keys["ar"] ^ keys["en"])
            err(f"i18n/features/{slug}: ar and en keys differ: {diff[:3]}")


def main():
    flags = (load(FE / "data" / "features.json") or {}).get("features", {})
    check_data(flags)
    check_modules(flags)
    check_namespaces(flags)
    if errors:
        print("FEATURE DATA CHECK FAILED")
        print("\n".join(errors))
        return 1
    print("OK: feature data, modules and namespaces")
    return 0


if __name__ == "__main__":
    sys.exit(main())

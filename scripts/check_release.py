# File: scripts/check_release.py
"""A35 step 3: every enabled feature's static files answer 200 with no-cache.

Usage: python3 scripts/check_release.py https://wasteai.duckdns.org
Stdlib only. Read-only (GET requests). Exit 1 on any FAIL.
JS is required; css, data and the two i18n files are optional (404 = SKIP).
"""
import json
import sys
import urllib.error
import urllib.request


def fetch(url):
    req = urllib.request.Request(url, headers={"Accept-Encoding": "identity"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.headers.get("Cache-Control", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Cache-Control", ""), b""
    except OSError as e:
        return 0, str(e), b""


def enabled_features(doc):
    items = doc.get("features", doc)
    out = []
    for slug, cfg in items.items():
        if slug.startswith("_") or not isinstance(cfg, dict):
            continue
        if cfg.get("enabled") is True:
            out.append((slug, cfg.get("module", slug)))
    return out


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    base = sys.argv[1].rstrip("/")
    fails = 0

    def check(label, path, required):
        nonlocal fails
        code, cc, _ = fetch(base + path)
        if code == 404 and not required:
            print(f"SKIP {label} {path} (404, optional)")
        elif code == 200 and "no-cache" in cc.lower():
            print(f"PASS {label} {path}")
        else:
            fails += 1
            print(f"FAIL {label} {path} status={code} cache-control={cc!r}")

    code, _, body = fetch(base + "/data/features.json")
    if code != 200:
        print(f"FAIL /data/features.json status={code}")
        return 1
    try:
        feats = enabled_features(json.loads(body))
    except ValueError:
        print("FAIL /data/features.json is not valid JSON")
        return 1

    check("features", "/data/features.json", True)
    if not feats:
        print("NOTE no feature has enabled: true (M48 decides the flags)")
    for slug, mod in feats:
        check(slug, f"/js/features/{mod}.js", True)
        check(slug, f"/css/features/{slug}.css", False)
        check(slug, f"/data/{slug}.json", False)
        for lang in ("ar", "en"):
            check(slug, f"/i18n/features/{slug}.{lang}.json", False)

    print(f"{fails} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

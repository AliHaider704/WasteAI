# File: scripts/a7a_web_photos.sh
#!/usr/bin/env bash
# Downloads a few public photos per category from Wikimedia Commons, runs
# a7a_baseline.sh on them, saves the report, deletes everything it downloaded.
# Usage: bash scripts/a7a_web_photos.sh          (N=4 photos per category)
#        N=6 bash scripts/a7a_web_photos.sh
set -u

REPO="${REPO:-/home/ubuntu/WasteAI}"
N="${N:-4}"
TMP="$(mktemp -d /tmp/a7a_web.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT
[ -f "$REPO/scripts/a7a_baseline.sh" ] || { echo "FAIL: $REPO/scripts/a7a_baseline.sh missing"; exit 1; }

echo "== downloading up to $N photos per category (Wikimedia Commons) =="
export TMP N
python3 - <<'PY'
import json, os, time, urllib.request, urllib.parse
from pathlib import Path

TMP = Path(os.environ["TMP"]) / "photos"; N = int(os.environ["N"])
UA = {"User-Agent": "WasteAI-fieldtest/1.0 (private evaluation; contact: project owner)"}
TERMS = {
    "plastic_pet": "plastic water bottle", "plastic_hdpe": "milk jug plastic",
    "plastic_pp": "plastic food container", "plastic_ldpe": "plastic carrier bag",
    "plastic_ps": "polystyrene foam packaging", "paper": "newspaper stack",
    "cardboard": "cardboard boxes", "carton_beverage": "juice carton",
    "glass": "glass bottle", "metal_aluminum": "aluminum drink can",
    "metal_steel": "tin can food", "organic_food": "food waste scraps",
    "organic_garden": "garden waste leaves", "ewaste_small": "old mobile phone",
    "ewaste_large": "discarded refrigerator", "battery": "used batteries",
    "textile": "old clothes pile", "hazardous_chemical": "paint can",
    "medical": "syringe", "wood": "wood pallet",
    "construction": "construction debris", "general_residual": "household garbage",
}

def fetch(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return r.read()
        except Exception as e:
            time.sleep(3 * (i + 1))
    return None

total = 0
for cat, term in TERMS.items():
    q = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"{term} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": 25,
        "prop": "imageinfo", "iiprop": "url|mime|size", "iiurlwidth": 800})
    raw = fetch("https://commons.wikimedia.org/w/api.php?" + q)
    if not raw:
        print(f"{cat}: search failed"); continue
    pages = sorted(json.loads(raw).get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
    d = TMP / cat; d.mkdir(parents=True, exist_ok=True); got = 0
    for p in pages:
        if got >= N: break
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("mime") != "image/jpeg": continue
        data = fetch(ii.get("thumburl") or ii.get("url", ""))
        time.sleep(1)
        if not data or len(data) > 2 * 1024 * 1024 or data[:3] != b"\xff\xd8\xff": continue
        (d / f"{cat}_{got}.jpg").write_bytes(data); got += 1
    total += got
    print(f"{cat}: {got}/{N}", flush=True)
print("downloaded:", total)
PY

COUNT=$(find "$TMP/photos" -type f 2>/dev/null | wc -l)
[ "$COUNT" -gt 0 ] || { echo "FAIL: nothing downloaded (no internet or Commons blocked)"; exit 1; }

# run the baseline with a temporary repo dir so real reports are not overwritten
mkdir -p "$TMP/repo/docs"
REPO="$TMP/repo" PHOTOS="$TMP/photos" bash "$REPO/scripts/a7a_baseline.sh"
RC=$?

if [ -f "$TMP/repo/docs/FIELD_TEST_BASELINE.md" ]; then
  OUT="$REPO/docs/FIELD_TEST_WEB_PHOTOS.md"
  { echo "<!-- File: docs/FIELD_TEST_WEB_PHOTOS.md -->"; echo "> Public Wikimedia Commons photos, NOT the owner's phone photos. Smoke test only, not the A7a baseline."; echo; tail -n +2 "$TMP/repo/docs/FIELD_TEST_BASELINE.md"; } > "$OUT"
  echo "Report: $OUT"
fi
echo "Cleanup: downloaded photos and temp files removed on exit."
exit $RC

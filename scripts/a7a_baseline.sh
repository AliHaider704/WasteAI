# File: scripts/a7a_baseline.sh
#!/usr/bin/env bash
# Phase A7a: baseline field test. Standard library only, no installs.
# Usage:  bash a7a_baseline.sh            (defaults below)
#         REPO=/path BASE=https://host bash a7a_baseline.sh
# Cleans its temp dir on exit. Touches only docs/FIELD_TEST_*.md in the repo.
set -u

REPO="${REPO:-/home/ubuntu/WasteAI}"
BASE="${BASE:-https://wasteai.duckdns.org}"
PHOTOS="${PHOTOS:-$REPO/server/eval_photos}"
TMP="$(mktemp -d /tmp/a7a.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

echo "== A7a baseline =="
[ -d "$PHOTOS" ] || { echo "FAIL: no photo folder: $PHOTOS (use eval_photos/<category_id>/*.jpg)"; exit 1; }
N=$(find "$PHOTOS" -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) | wc -l)
[ "$N" -gt 0 ] || { echo "FAIL: 0 photos found in $PHOTOS"; exit 1; }
echo "photos: $N  base: $BASE"
H=$(curl -s -m 10 "$BASE/api/v1/health") || true
echo "health: ${H:-NO ANSWER}"
case "$H" in *'"status"'*) ;; *) echo "FAIL: site not answering"; exit 1;; esac
echo "RAM before: $(free -m | awk '/Mem:/{print $7" MB available"}')"
echo "est. time: about $(( N * 7 / 60 + 1 )) min (6.5 s per photo for the 10/min limit)"

export REPO BASE PHOTOS TMP HEALTH="$H"
python3 - <<'PY'
import json, os, sys, time, uuid, statistics, subprocess, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone

BASE = os.environ["BASE"]; PHOTOS = Path(os.environ["PHOTOS"]); REPO = Path(os.environ["REPO"])
HAZ = {"battery", "hazardous_chemical", "medical", "ewaste_small", "ewaste_large"}
MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
DELAY = 6.5

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=15) as r:
        return json.load(r)

def post(path, fp):
    b = uuid.uuid4().hex
    data = fp.read_bytes()
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{fp.name}\"\r\n"
            f"Content-Type: {MIME[fp.suffix.lower()]}\r\n\r\n").encode() + data + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(BASE + path, data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, json.load(r), {}
    except urllib.error.HTTPError as e:
        try: j = json.load(e)
        except Exception: j = {}
        return e.code, j, dict(e.headers)

try:
    cats = get("/api/v1/categories?lang=en")["categories"]
    group_of = {c["id"]: c["group"] for c in cats}
except Exception as e:
    print("WARN: categories not loaded:", e); group_of = {}

files = []
for d in sorted(p for p in PHOTOS.iterdir() if p.is_dir()):
    for f in sorted(d.iterdir()):
        if f.suffix.lower() in MIME:
            files.append((d.name, f))

rows, skipped, errors = [], [], []
t_start = time.time()
for i, (truth, fp) in enumerate(files, 1):
    if truth not in group_of and group_of:
        skipped.append(f"{truth}/{fp.name}: unknown category folder"); continue
    if fp.stat().st_size > 2 * 1024 * 1024:
        skipped.append(f"{truth}/{fp.name}: over 2 MB"); continue
    code, j, hdr = 0, {}, {}
    t0 = time.time()
    for attempt in range(4):
        t0 = time.time()
        try:
            code, j, hdr = post("/api/v1/classify?lang=en", fp)
        except Exception as e:
            code, j, hdr = -1, {"error": {"code": str(e)[:60]}}, {}
        if code == 429:
            time.sleep(min(int(hdr.get("Retry-After", 10)) + 1, 70)); continue
        break
    lat = time.time() - t0
    if code != 200:
        errors.append((truth, fp.name, code, (j.get("error") or {}).get("code", "?")))
        rows.append({"truth": truth, "http": code, "lat": lat}); 
    else:
        cat = j.get("category") or {}
        alts = [a["id"] for a in j.get("alternatives", [])]
        rows.append({"truth": truth, "http": 200, "status": j.get("status"), "pred": cat.get("id"),
                     "group": cat.get("group"), "alts": alts, "hazard": bool(j.get("hazard")),
                     "agree": j.get("agreement"), "lat": lat,
                     "src": {s["name"]: s["ok"] for s in j.get("sources", [])}})
    print(f"[{i}/{len(files)}] {truth}/{fp.name} -> {code} {rows[-1].get('status','')} {rows[-1].get('pred','')}", flush=True)
    time.sleep(DELAY)

ok200 = [r for r in rows if r["http"] == 200]
n = len(ok200)
def pct(a, b): return f"{100*a/b:.1f}% ({a}/{b})" if b else "n/a"
okr = [r for r in ok200 if r["status"] == "ok"]
unc = [r for r in ok200 if r["status"] == "uncertain"]
top1 = sum(1 for r in ok200 if r["pred"] == r["truth"])
acc_ok = sum(1 for r in okr if r["pred"] == r["truth"])
grp = sum(1 for r in okr if r["group"] == group_of.get(r["truth"]))
top2 = sum(1 for r in ok200 if r["pred"] == r["truth"] or r["truth"] in r["alts"])
hz = [r for r in ok200 if r["truth"] in HAZ]
hz_hit = sum(1 for r in hz if r["hazard"])
lats = sorted(r["lat"] for r in rows)
med = statistics.median(lats) if lats else 0
p95 = lats[min(len(lats) - 1, int(0.95 * len(lats)))] if lats else 0
srcs = {}
for r in ok200:
    for k, v in r["src"].items():
        a = srcs.setdefault(k, [0, 0]); a[1] += 1; a[0] += 1 if v else 0

conf = {}
for r in ok200:
    c = conf.setdefault(r["truth"], {"n": 0, "ok": 0, "unc": 0, "wrong": {}})
    c["n"] += 1
    if r["status"] == "uncertain": c["unc"] += 1
    elif r["pred"] == r["truth"]: c["ok"] += 1
    else: c["wrong"][r["pred"]] = c["wrong"].get(r["pred"], 0) + 1

def sh(cmd):
    try: return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception: return ""
mem = sh("systemctl show wasteai -p MemoryCurrent -p MemoryPeak 2>/dev/null") or "not available (not run on the host)"
health = os.environ.get("HEALTH", "")

L = ["<!-- File: docs/FIELD_TEST_BASELINE.md -->",
     "# Field test baseline (A7a)", "",
     f"Generated by a7a_baseline.sh, not hand-written. Date: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. Base: {BASE}.",
     f"Health at start: `{health}`", "",
     "| Metric | Result |", "|---|---|",
     f"| Photos found | {len(files)} |", f"| Photos answered (HTTP 200) | {n} |",
     f"| Skipped | {len(skipped)} |", f"| Errors (non-200) | {len(errors)} |",
     f"| Top-1 accuracy (all answered) | {pct(top1, n)} |",
     f"| Accuracy on `ok` | {pct(acc_ok, len(okr))} |",
     f"| Group accuracy on `ok` | {pct(grp, len(okr))} |",
     f"| Top-2 recall (incl. alternatives) | {pct(top2, n)} |",
     f"| `uncertain` rate | {pct(len(unc), n)} |",
     f"| Hazard recall (hazard flag on hazard photos) | {pct(hz_hit, len(hz))} |",
     f"| Latency median / p95 (client wall time) | {med:.2f} s / {p95:.2f} s |",
     f"| Run time | {(time.time()-t_start)/60:.1f} min |", "",
     "## Source availability", ""]
L += [f"- `{k}`: ok on {pct(a, b)}" for k, (a, b) in sorted(srcs.items())] or ["- none recorded"]
L += ["", "## Per-category result", "", "| Category | Photos | Correct | Uncertain | Wrong (predicted: count) |", "|---|---|---|---|---|"]
for k, c in sorted(conf.items()):
    w = ", ".join(f"{p}: {v}" for p, v in sorted(c["wrong"].items(), key=lambda x: -x[1])) or "-"
    L.append(f"| {k} | {c['n']} | {c['ok']} | {c['unc']} | {w} |")
L += ["", "## Memory (host)", "", "```", mem, "```", ""]
if errors:
    L += ["## Errors", ""] + [f"- {t}/{f}: HTTP {c} {m}" for t, f, c, m in errors[:50]] + [""]
if skipped:
    L += ["## Skipped", ""] + [f"- {s}" for s in skipped[:50]] + [""]
L += ["## Notes", "",
      "- Baseline before A14 tuning. Numbers are from this run only, on the owner's photos; no extrapolation.",
      "- If `local_onnx` is `down`, this is an Azure-only baseline (single source needs 0.80).",
      "- Do not edit this file by hand."]
text = "\n".join(L) + "\n"
docs = REPO / "docs"; docs.mkdir(exist_ok=True)
(docs / "FIELD_TEST_BASELINE.md").write_text(text, encoding="utf-8")
(docs / "FIELD_TEST_REPORT.md").write_text(text.replace("FIELD_TEST_BASELINE.md", "FIELD_TEST_REPORT.md", 1), encoding="utf-8")
print("\n" + "\n".join(L[6:20]))
PY
RC=$?
echo "RAM after: $(free -m | awk '/Mem:/{print $7" MB available"}')"
echo "services: nginx=$(systemctl is-active nginx) wasteai=$(systemctl is-active wasteai)"
[ $RC -eq 0 ] && echo "DONE: $REPO/docs/FIELD_TEST_BASELINE.md (+ FIELD_TEST_REPORT.md). Temp dir removed." || echo "FAILED (code $RC)"
exit $RC

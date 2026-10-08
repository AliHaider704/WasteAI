# File: scripts/health_prove.sh
#!/usr/bin/env bash
# Proves both paths with a real inference. Usage: bash scripts/health_prove.sh /path/photo.jpg [base_url]
# Deep check is read from the loopback port (Nginx allows 127.0.0.1 only).
set -u
PHOTO="${1:-}"; BASE="${2:-https://wasteai.duckdns.org}"; LOCAL="${LOCAL_URL:-http://127.0.0.1:8100}"
[ -f "$PHOTO" ] || { echo "usage: $0 photo.jpg [base_url]"; exit 2; }
echo "== public health"; curl -s "$BASE/api/v1/health"; echo
echo "== deep (local port)"; curl -s "$LOCAL/api/v1/health/deep"; echo
echo "== deep from outside (expect 403/404)"; curl -s -o /dev/null -w "%{http_code}\n" "$BASE/api/v1/health/deep"
echo "== real photo through /classify"
curl -s -F "image=@$PHOTO" -w "\nhttp=%{http_code} total=%{time_total}s\n" "$LOCAL/api/v1/classify?lang=en" |
python3 -c '
import sys, json
raw = sys.stdin.read(); body, _, tail = raw.rpartition("\nhttp=")
d = json.loads(body)
if "error" in d: print("ERROR", d["error"]["code"]); sys.exit(1)
for s in d["sources"]: print(f"{s['"'"'name'"'"']:10} ok={s['"'"'ok'"'"']}")
print("status", d["status"], "agreement", d["agreement"], "elapsed_ms", d["elapsed_ms"], "| http="+tail)'

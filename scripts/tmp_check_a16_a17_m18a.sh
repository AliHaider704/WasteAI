# File: scripts/tmp_check_a16_a17_m18a.sh
#!/usr/bin/env bash
# TEMPORARY: runs the checkable "Done when" items of A16, A17 and M18a. Delete after use.
# Run from the repo root on the host: bash scripts/tmp_check_a16_a17_m18a.sh [domain]
D="${1:-wasteai.duckdns.org}"; U="https://$D"; P=0; F=0
ok(){ echo "PASS  $1"; P=$((P+1)); }; no(){ echo "FAIL  $1"; F=$((F+1)); }
chk(){ local n="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$n"; else no "$n"; fi; }
has(){ local n="$1" url="$2" re="$3"; curl -sI "$url" | grep -qiE "$re" && ok "$n" || no "$n"; }
PY=python3; [ -x server/.venv/bin/python ] && PY=server/.venv/bin/python

echo "== A16 =="
chk "pytest"              bash -c "cd server && python3 -m pytest -q"
chk "ruff"              bash -c "cd server && python3 -m ruff check ."
chk "check_paths"       python3 scripts/check_paths.py
chk "check_lines"       bash scripts/check_lines.sh
chk "check_hygiene"     python3 scripts/check_hygiene.py
[ -z "$(git ls-files 2>/dev/null | grep -E 'env\.example$|\.db$' | grep -v '^server/\.env\.example$')" ] && ok "no stray env/db tracked" || no "stray env/db tracked"
[ -z "$(git ls-files 2>/dev/null | grep -E '\.zip$')" ] && ok "no zip tracked" || no "zip tracked"

echo "== A17 (live) =="
has "app.js no-cache"      "$U/js/app.js" "cache-control:.*no-cache"
has "index no-cache"       "$U/"          "cache-control:.*no-cache"
FONT=$(cd /home/ubuntu/waste_ai/frontend 2>/dev/null && find assets/fonts -name '*.woff2' | head -1)
has "font immutable"       "$U/$FONT"     "cache-control:.*immutable"
for h in strict-transport-security cross-origin-opener-policy cross-origin-resource-policy x-content-type-options referrer-policy permissions-policy; do has "header $h" "$U/" "^$h"; done
curl -sI "$U/" | grep -i '^server:' | grep -qE '[0-9]\.[0-9]' && no "server header shows version" || ok "server header has no version"
CODES=$(for i in $(seq 12); do curl -s -o /dev/null -w "%{http_code} " -X POST "$U/api/v1/classify"; done)
echo "      classify x12: $CODES"; [ "$(echo $CODES | awk '{print $NF}')" = "429" ] && ok "classify ends in 429" || no "classify ends in 429"
head -c 3600000 /dev/urandom > /tmp/big.jpg
curl -s -F image=@/tmp/big.jpg "$U/api/v1/classify" | grep -q image_too_large && ok "big upload -> image_too_large JSON" || no "big upload JSON"
rm -f /tmp/big.jpg
sudo nginx -t >/dev/null 2>&1 && ok "nginx -t" || no "nginx -t"
OUT=$(bash deploy/install.sh --fix-owner 2>&1 | tail -3); echo "$OUT" | grep -qE ': 0|^0' && ok "fix-owner 0" || { echo "$OUT"; no "fix-owner 0"; }
echo "      sleeping 60s for feedback limiter..."; sleep 60
FB=$(for i in $(seq 10); do curl -s -o /dev/null -w "%{http_code} " -X POST -H 'Content-Type: application/json' -d '{}' "$U/api/v1/feedback"; done)
echo "      feedback x10: $FB"; [[ "$FB" == *429* ]] && ok "feedback hits 429" || no "feedback hits 429"

echo "== M18a (scriptable part) =="
chk "node --check frontend/js"  bash -c 'for f in frontend/js/*.js; do node --check "$f" || exit 1; done'
chk "check_paths frontend content" python3 scripts/check_paths.py frontend content
chk "check_content"             python3 content/tools/check_content.py
N=$(grep -c "i18n:change" frontend/js/app.js 2>/dev/null); [ "${N:-0}" -ge 1 ] && ok "app.js has i18n:change ($N)" || no "app.js lacks i18n:change"
[ -f content/notes/leak_root_cause.md ] && ok "leak_root_cause.md exists" || no "leak_root_cause.md missing (needs a browser)"
curl -s "$U/js/app.js" | grep -q "^<<<<<<<\|^>>>>>>>" && no "merge markers served" || ok "no merge markers served"
curl -s "$U/js/app.js" | grep -q "i18n:change" && ok "served app.js has i18n:change" || no "served app.js is the OLD version (run install.sh)"
LAT=$(curl -s "$U/api/v1/categories?lang=ar" | python3 -c "import sys,json;d=json.load(sys.stdin);print(sum(1 for c in d['categories'] if any('a'<=ch.lower()<='z' for ch in c['name'])))" 2>/dev/null)
[ "$LAT" = "0" ] && ok "categories?lang=ar: 0 Latin names" || no "categories?lang=ar Latin names: ${LAT:-error}"
echo; echo "PASS=$P FAIL=$F"; echo "NOT scriptable (browser): Browse ar/en toggle x5, ?group=glass chip, API-stopped Retry state, Network shows /categories?lang=ar"
[ "$F" -eq 0 ]

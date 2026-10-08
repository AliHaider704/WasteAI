# File: scripts/fix_cache.sh
#!/bin/bash
set -u
: "${EMAIL:?set EMAIL=<your address> before running}"
cd ~/WasteAI || exit 1
T=deploy/templates/nginx.conf.tpl

echo "== 1) merge markers anywhere?"
if grep -rnE '^(<<<<<<<|=======$|>>>>>>>)' frontend content server contract deploy scripts --include='*' 2>/dev/null | grep -v '\.woff2'; then
  echo "FOUND markers above. Stop."; exit 1
fi
echo "none"

echo "== 2) add Cache-Control no-cache to location / (idempotent)"
if ! grep -q 'Cache-Control "no-cache"' "$T"; then
python3 - <<'PY'
p="deploy/templates/nginx.conf.tpl"
s=open(p,encoding="utf-8").read()
old="""    location / {
        include /etc/nginx/snippets/wasteai-headers.conf;
"""
new=old+"""        add_header Cache-Control "no-cache" always;
"""
assert old in s
open(p,"w",encoding="utf-8").write(s.replace(old,new,1))
PY
fi
grep -n 'Cache-Control' "$T"
# add_header in a location drops inherited ones, so the snippet is included in the same block (already is).

echo "== 3) deploy"
bash deploy/install.sh --domain wasteai.duckdns.org --email "$EMAIL"

echo "== 4) verify from outside"
U=https://wasteai.duckdns.org
for f in index.html js/app.js css/base.css; do
  echo "-- $f"; curl -sI "$U/$f" | grep -iE '^HTTP|cache-control|last-modified|content-security'
done
echo "markers in served app.js (must be 0): $(curl -s $U/js/app.js | grep -cE '^(<<<<<<<|=======$|>>>>>>>)')"
echo "Inter-Variable in served base.css (must be 0): $(curl -s $U/css/base.css | grep -c 'Inter-Variable')"
echo "woff2 reachable:"
for f in plex-sans/ibm-plex-sans-latin-400-normal.woff2 plex-sans-arabic/ibm-plex-sans-arabic-arabic-400-normal.woff2; do
  curl -s -o /dev/null -w "%{http_code} $f\n" "$U/assets/fonts/$f"
done
echo "api:"; curl -s $U/api/v1/health; echo

echo "== 5) push"
git add "$T"
git commit -m "deploy: no-cache for static files" && git push || echo "push failed (site is fine)"
echo "DONE. On your device: F12 > Application > Storage > Clear site data, then reload."

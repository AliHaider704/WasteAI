#!/usr/bin/env bash
# a44_setup.sh: run ONCE on the server after "git pull". Safe to run again.
# Usage: bash a44_setup.sh [/path/to/WasteAI]   (default: current folder)
#        RESTART=1 bash a44_setup.sh            (also restarts the wasteai service)
set -eu
REPO="${1:-$PWD}"
RULES="$REPO/server/data/label_rules"
[ -d "$RULES" ] || { echo "FAIL: $RULES not found (give the repo path)"; exit 1; }

mkdir -p "$RULES/hand" "$RULES/seed" "$RULES/learned"
touch "$RULES/seed/.gitkeep" "$RULES/learned/.gitkeep"

# 1. move the old rule files into hand/ (the 10 files sitting directly in label_rules/)
moved=0
for f in "$RULES"/*.json; do
  [ -e "$f" ] || continue
  name="$(basename "$f")"
  [ "$name" = "_scale.json" ] && continue
  if [ -e "$RULES/hand/$name" ]; then rm -f "$f"; else mv "$f" "$RULES/hand/$name"; fi
  moved=$((moved + 1))
done
echo "moved: $moved file(s) into hand/"

# 2. fix the "_path" line inside each hand file
for f in "$RULES"/hand/*.json; do
  name="$(basename "$f")"
  sed -i "s#\"_path\": *\"[^\"]*\"#\"_path\": \"server/data/label_rules/hand/$name\"#" "$f"
done

# 3. scale file (only created if missing)
if [ ! -f "$RULES/_scale.json" ]; then
cat > "$RULES/_scale.json" <<'JSON'
{"_path": "server/data/label_rules/_scale.json",
 "scale": {"hand": 1.0, "seed": 0.5, "learned": 0.5}}
JSON
echo "created _scale.json"
fi

# 4. check
cd "$REPO/server"
PY="python3"; [ -x "$REPO/server/.venv/bin/python" ] && PY="$REPO/server/.venv/bin/python"
ls "$RULES/hand" | wc -l | xargs echo "hand files:"
$PY -c "from app import mapper; print('rules loaded:', len(mapper.load_rules()))"
if $PY -m pytest --version >/dev/null 2>&1; then $PY -m pytest -q 2>&1 | tail -4; else echo "pytest not installed: tests skipped"; fi

# 5. optional restart
if [ "${RESTART:-0}" = "1" ]; then
  sudo systemctl restart wasteai && sleep 2
  curl -s -m 10 http://127.0.0.1:8000/api/v1/health || echo "(health check: adjust port/URL)"
  echo
fi
echo "DONE"

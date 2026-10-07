# File: scripts/parity_check.sh
#!/usr/bin/env bash
# Read-only local vs VPS parity check. Prints PASS/FAIL/SKIP per item, exits 1 on any FAIL.
# Mode is detected: if /home/ubuntu/waste_ai exists the script runs as HOST, else LOCAL.
# Usage: bash scripts/parity_check.sh [--app DIR] [--python PY] [--local-base URL] [--public-base URL]
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="" ; PY="" ; LOCAL_BASE="http://localhost:8100" ; PUBLIC_BASE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --app) APP="$2"; shift 2 ;;
    --python) PY="$2"; shift 2 ;;
    --local-base) LOCAL_BASE="$2"; shift 2 ;;
    --public-base) PUBLIC_BASE="$2"; shift 2 ;;
    -h|--help) sed -n '2,5p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$APP" ]; then
  if [ -d /home/ubuntu/waste_ai ]; then APP=/home/ubuntu/waste_ai; MODE=HOST; else APP="$ROOT"; MODE=LOCAL; fi
else
  [ "$APP" = "$ROOT" ] && MODE=LOCAL || MODE=HOST
fi
if [ -z "$PY" ]; then
  if [ -x "$APP/.venv/bin/python" ]; then PY="$APP/.venv/bin/python"
  elif [ -x "$ROOT/server/.venv/bin/python" ]; then PY="$ROOT/server/.venv/bin/python"
  else PY="$(command -v python3 || true)"; fi
fi
ENV_FILE="$APP/server/.env"
FAILS=0

pass() { printf 'PASS  %s\n' "$1"; }
skip() { printf 'SKIP  %s (%s)\n' "$1" "$2"; }
fail() { printf 'FAIL  %s (%s)\n' "$1" "$2"; FAILS=$((FAILS + 1)); }
norm() { tr 'A-Z_' 'a-z-' ; }
env_get() { [ -f "$ENV_FILE" ] && grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- | tr -d '"' || true; }

echo "== parity_check: mode=$MODE app=$APP python=${PY:-none}"

# 1. Python minor version
if [ -z "$PY" ]; then fail "python minor is 3.12" "no python found"
else
  v="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>&1)"
  [ "$v" = "3.12" ] && pass "python minor is 3.12" || fail "python minor is 3.12" "found $v"
fi

# 2. Pinned packages and pip check
REQ="$ROOT/server/requirements.txt"
if [ -z "$PY" ] || ! "$PY" -m pip --version >/dev/null 2>&1; then
  fail "pinned packages match requirements.txt" "pip not available for $PY"
else
  frz="$("$PY" -m pip freeze 2>/dev/null | norm | sort)"
  missing=""
  while IFS= read -r line; do
    case "$line" in ''|'#'*) continue ;; esac
    want="$(printf '%s' "$line" | norm)"
    printf '%s\n' "$frz" | grep -qxF "$want" || missing="$missing $line"
  done < "$REQ"
  [ -z "$missing" ] && pass "pinned packages match requirements.txt" || fail "pinned packages match requirements.txt" "differs:$missing"
  out="$("$PY" -m pip check 2>&1)"
  [ "$out" = "No broken requirements found." ] && pass "pip check clean" || fail "pip check clean" "$out"
fi

# 3. Env variable names
EX="$ROOT/server/.env.example"
if [ ! -f "$ENV_FILE" ]; then
  [ "$MODE" = HOST ] && fail "env names match .env.example" "$ENV_FILE missing" || skip "env names match .env.example" "no local .env"
else
  gone="$(comm -23 <(grep -o '^[A-Z_0-9]*' "$EX" | sort -u) <(grep -o '^[A-Z_0-9]*' "$ENV_FILE" | sort -u) | tr '\n' ' ')"
  [ -z "$gone" ] && pass "env names match .env.example" || fail "env names match .env.example" "missing in .env: $gone"
fi

# 4. Layout
miss=""
for d in server frontend content contract; do [ -d "$APP/$d" ] || miss="$miss $d"; done
[ -z "$miss" ] && pass "layout has server frontend content contract" || fail "layout has server frontend content contract" "missing:$miss"
if [ "$MODE" = HOST ]; then
  for d in server frontend content contract; do [ -d "$ROOT/$d" ] || { fail "repo clone layout" "missing $d in $ROOT"; break; }; done
fi

# 5. Start command
UNIT="$ROOT/deploy/templates/wasteai.service"
exec_line="$(grep '^ExecStart=' "$UNIT" || true)"
ok=1
for need in "--workers 1" "--proxy-headers" "--port __PORT__" "app.main:app"; do
  printf '%s' "$exec_line" | grep -qF -- "$need" || { ok=0; fail "unit ExecStart has '$need'" "$exec_line"; }
done
iport="$(grep -oE 'PORT[:=-]+"?[0-9]{4}' "$ROOT/deploy/install.sh" | grep -oE '[0-9]{4}' | head -1)"
rport="$(grep -h 'uvicorn' "$ROOT/README.md" | grep -oE -- '--port [0-9]+' | head -1 | grep -oE '[0-9]+')"
if [ -z "$rport" ]; then fail "README quick start uses uvicorn" "no uvicorn command in README.md"
elif [ -n "$iport" ] && [ "$rport" != "$iport" ]; then fail "README port equals installer port" "README $rport, install.sh $iport"
else pass "README port equals installer port ($rport)"; fi
[ "$ok" = 1 ] && pass "unit ExecStart: 1 worker, proxy headers, app.main:app"

# 6. Model file hash
MODEL="$(env_get MODEL_PATH)"; [ -z "$MODEL" ] && MODEL="$APP/models/model.onnx"
SHA="$(env_get MODEL_SHA256)"; [ -z "$SHA" ] && SHA="$(env_get MODEL_SHA)"
if [ ! -f "$MODEL" ]; then
  [ "$MODE" = HOST ] && fail "model sha256 equals MODEL_SHA256" "no model at $MODEL" || skip "model sha256 equals MODEL_SHA256" "no model file locally"
elif [ -z "$SHA" ]; then fail "model sha256 equals MODEL_SHA256" "MODEL_SHA256 empty"
else
  got="$(sha256sum "$MODEL" | cut -d' ' -f1)"
  [ "$got" = "$SHA" ] && pass "model sha256 equals MODEL_SHA256" || fail "model sha256 equals MODEL_SHA256" "got $got"
fi

# 7. Headers (CSP and nosniff identical on local and public base)
hdr() { curl -sI -m 8 "$1/api/v1/health" 2>/dev/null | tr -d '\r' | grep -iE '^(content-security-policy|x-content-type-options):' | tr 'A-Z' 'a-z' | sort; }
if [ -f "$ROOT/scripts/field_test.py" ] && curl -s -m 5 -o /dev/null "$LOCAL_BASE/api/v1/health"; then
  "$PY" "$ROOT/scripts/field_test.py" headers --base "$LOCAL_BASE" >/dev/null 2>&1 \
    && pass "field_test headers on $LOCAL_BASE" || fail "field_test headers on $LOCAL_BASE" "non-zero exit"
else skip "field_test headers" "field_test.py missing or $LOCAL_BASE not reachable"; fi
if [ -n "$PUBLIC_BASE" ]; then
  a="$(hdr "$LOCAL_BASE")"; b="$(hdr "$PUBLIC_BASE")"
  if [ -z "$a" ] || [ -z "$b" ]; then skip "CSP and nosniff equal local vs public" "a base did not answer"
  elif [ "$a" = "$b" ]; then pass "CSP and nosniff equal local vs public"
  else fail "CSP and nosniff equal local vs public" "header sets differ"; fi
else skip "CSP and nosniff equal local vs public" "no --public-base"; fi

# 8. Content check, 9. Cap rules
if [ -n "$PY" ] && (cd "$ROOT" && "$PY" content/tools/check_content.py >/dev/null 2>&1); then pass "check_content.py"; else fail "check_content.py" "failed"; fi
if (cd "$ROOT" && bash scripts/check_lines.sh >/dev/null 2>&1); then pass "check_lines.sh"; else fail "check_lines.sh" "failed"; fi
if [ -n "$PY" ] && (cd "$ROOT" && "$PY" scripts/check_paths.py server deploy scripts >/dev/null 2>&1); then pass "check_paths.py"; else fail "check_paths.py" "failed"; fi

# 10. Headroom
if command -v free >/dev/null 2>&1; then
  avail="$(free -m | awk '/^Mem:/ {print $7}')"
  [ "${avail:-0}" -gt 150 ] && pass "free RAM above 150 MB (${avail} MB)" || fail "free RAM above 150 MB" "${avail:-unknown} MB"
else skip "free RAM above 150 MB" "free not available"; fi

echo "== result: $FAILS failure(s)"
[ "$FAILS" -eq 0 ]

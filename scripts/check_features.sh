# File: scripts/check_features.sh
#!/usr/bin/env bash
# Delight-track guards: standard checks S, size budgets, storage and safety greps, UI greps (overview 4.5).
# Every check runs; exit 1 if any failed. Checks whose target does not exist yet are skipped, not passed.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
bad=0
fail() { echo "FAIL: $*"; bad=1; }
run() { local name="$1"; shift; if "$@" >/tmp/cf.out 2>&1; then echo "ok: $name"; else fail "$name"; tail -n 8 /tmp/cf.out; fi; }

# --- S: standard checks (frontend side) ---
if ls frontend/js/*.js >/dev/null 2>&1; then
  files=$(ls frontend/js/*.js frontend/js/features/*.js 2>/dev/null)
  if command -v node >/dev/null; then
    ok=1; for f in $files; do node --check "$f" >/dev/null 2>&1 || { fail "node --check $f"; ok=0; }; done
    [ "$ok" -eq 1 ] && echo "ok: node --check"
  else echo "skip: node not installed"; fi
fi
run "check_content" python3 content/tools/check_content.py
run "check_ui_leaks" python3 content/tools/check_ui_leaks.py
if [ -f content/tools/check_feature_data.py ]; then run "check_feature_data" python3 content/tools/check_feature_data.py
else echo "skip: check_feature_data.py (arrives with M31)"; fi
run "check_lines" bash scripts/check_lines.sh
run "check_budget" python3 scripts/check_budget.py

# --- storage: only features/store.js and the existing settings files may touch web storage ---
hits=$(grep -rlE "localStorage|sessionStorage" frontend/js 2>/dev/null \
  | grep -vE "features/store\.js|/theme\.js|/i18n\.js|/audio\.js|/contrast\.js" || true)
if [ -n "$hits" ]; then fail "web storage outside store.js and the settings files:"; echo "$hits"; else echo "ok: storage"; fi

# --- feature files only (skipped while the folders do not exist) ---
JS=frontend/js/features; CSS=frontend/css/features
if [ ! -d "$JS" ] && [ ! -d "$CSS" ]; then
  echo "skip: feature greps (no frontend/js/features or frontend/css/features yet)"
else
  scan() { # name, regex, paths...
    local name="$1" re="$2"; shift 2
    local out; out=$(grep -rnE --include='*.js' --include='*.css' --include='*.json' "$re" "$@" 2>/dev/null || true)
    if [ -n "$out" ]; then fail "$name"; echo "$out" | head -n 8; else echo "ok: $name"; fi
  }
  DIRS=""; [ -d "$JS" ] && DIRS="$DIRS $JS"; [ -d "$CSS" ] && DIRS="$DIRS $CSS"
  # shellcheck disable=SC2086
  {
    scan "no fetch to absolute http" 'fetch\(\s*["'"'"'`]https?:' $JS
    scan "no eval" '(^|[^A-Za-z_.])eval\(' $JS
    scan "no new Function" 'new Function' $JS
    scan "no innerHTML assigned a variable" 'innerHTML\s*=\s*[^"'"'"'`[:space:];]' $JS
    scan "no inline style attribute" 'style=|setAttribute\(\s*["'"'"']style' $DIRS
    scan "no transition: all" 'transition:\s*all' $DIRS
    scan "no uppercase text" 'text-transform:\s*uppercase' $DIRS
    scan "no linear-gradient" 'linear-gradient' $DIRS
    scan "no backdrop-filter" 'backdrop-filter' $DIRS
    scan "no div onclick" '<div[^>]*onclick' $JS
    scan "no three dots or em dash in strings" '\.\.\.|—' $JS
  }
  # outline: none needs a :focus-visible rule in the same file; animation needs a no-preference block
  for f in $(find $DIRS -name '*.css' 2>/dev/null); do
    grep -qE 'outline:\s*none' "$f" && ! grep -q ':focus-visible' "$f" && fail "outline: none without :focus-visible in $f"
    grep -qE '(^|[^-])animation(-name)?:' "$f" && ! grep -q 'prefers-reduced-motion:\s*no-preference' "$f" \
      && fail "animation outside prefers-reduced-motion: no-preference in $f"
  done
  echo "done: css file rules"
fi

[ "$bad" -eq 0 ] && echo "OK: feature checks passed"
exit "$bad"

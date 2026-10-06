# scripts/check_lines.sh
#!/usr/bin/env bash
# Fails if any tracked text file exceeds 500 lines.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LIMIT=500
bad=0
while IFS= read -r -d '' f; do
  n=$(wc -l < "$f")
  if [ "$n" -gt "$LIMIT" ]; then
    echo "TOO LONG ($n lines): ${f#"$ROOT"/}"
    bad=1
  fi
done < <(find "$ROOT" -type f \( -name '*.py' -o -name '*.md' -o -name '*.json' -o -name '*.yaml' \
  -o -name '*.yml' -o -name '*.css' -o -name '*.js' -o -name '*.html' -o -name '*.sh' -o -name '*.toml' \) \
  -not -path '*/.git/*' -not -path '*/.venv/*' -not -path '*/node_modules/*' -not -path '*/__pycache__/*' -print0)
[ "$bad" -eq 0 ] && echo "OK: all files <= $LIMIT lines"
exit "$bad"

#!/usr/bin/env bash
# File: scripts/rollout_a42.sh
# A42 host rollout: enable flags that passed G-C, ONE AT A TIME, measured, auto-revert on failure.
# Run on the host as user ubuntu from the repo clone (needs sudo for systemctl/journalctl only).
#
# Usage:
#   bash scripts/rollout_a42.sh --photo /tmp/p.jpg --flag MAPPER_V2=true [--flag WEIGHT_MODE=reliability ...]
#   bash scripts/rollout_a42.sh --rollback          # restore .env from the A42 backup, restart wasteai
#   bash scripts/rollout_a42.sh --status            # show current values of the five flags
# Only these flags are accepted: MAPPER_V2 WEIGHT_MODE POLICY_V2 AZURE_CAPTION CLIP_ENABLED
# It never edits .env with sudo, never restarts nginx/docker, never prints keys.
set -u

APP=/home/ubuntu/waste_ai
ENV="$APP/server/.env"
BAK="$APP/server/.env.a42.bak"
BASE=http://127.0.0.1:8100/api/v1
REPORT_DIR=docs/phases/accuracy/handoff
REPORT="$REPORT_DIR/rollout_report.md"
REPLAY=docs/FIELD_TEST_REPLAY.md
ALLOWED="MAPPER_V2 WEIGHT_MODE POLICY_V2 AZURE_CAPTION CLIP_ENABLED"
MIN_MEM=300   # MB MemAvailable gate

PHOTO=""; FLAGS=(); MODE=run
while [ $# -gt 0 ]; do
  case "$1" in
    --photo) PHOTO="${2:-}"; shift 2 ;;
    --flag) FLAGS+=("${2:-}"); shift 2 ;;
    --rollback) MODE=rollback; shift ;;
    --status) MODE=status; shift ;;
    *) echo "unknown argument: $1"; exit 2 ;;
  esac
done

mem() { awk '/MemAvailable/{printf "%d", $2/1024}' /proc/meminfo; }
get_kv() { grep -m1 "^$1=" "$ENV" 2>/dev/null | cut -d= -f2-; }
has_kv() { grep -q "^$1=" "$ENV" 2>/dev/null; }
set_kv() {
  if has_kv "$1"; then sed -i "s|^$1=.*|$1=$2|" "$ENV"; else printf '%s=%s\n' "$1" "$2" >>"$ENV"; fi
}
del_kv() { sed -i "/^$1=/d" "$ENV"; }
restart() { sudo systemctl restart wasteai; }
wait_up() {
  local i
  for i in $(seq 1 30); do
    if curl -fsS "$BASE/health" 2>/dev/null | grep -q '"local_onnx": *"up"'; then return 0; fi
    sleep 2
  done
  return 1
}
allowed() { local f; for f in $ALLOWED; do [ "$f" = "$1" ] && return 0; done; return 1; }

if [ "$MODE" = status ]; then
  for f in $ALLOWED; do printf '%s=%s\n' "$f" "$(get_kv "$f")"; done
  echo "MemAvailable: $(mem) MB"
  curl -fsS "$BASE/health"; echo
  exit 0
fi

if [ "$MODE" = rollback ]; then
  [ -f "$BAK" ] || { echo "no backup at $BAK"; exit 1; }
  cp "$BAK" "$ENV" && chmod 600 "$ENV"
  restart
  if wait_up; then echo "rollback OK: /health up"; else echo "rollback done but /health NOT up"; exit 1; fi
  bash deploy/install.sh --fix-owner
  exit 0
fi

# ---- run mode: gates ----
[ -f "$REPLAY" ] || { echo "STOP: $REPLAY missing (A36 replay never ran). No flag may be enabled without a G-C verdict."; exit 1; }
[ -f "$ENV" ] || { echo "STOP: $ENV not found"; exit 1; }
[ "${#FLAGS[@]}" -gt 0 ] || { echo "STOP: give at least one --flag NAME=VALUE that passed G-C"; exit 2; }
if [ -n "$PHOTO" ] && [ ! -f "$PHOTO" ]; then echo "STOP: photo $PHOTO not found"; exit 2; fi
for kv in "${FLAGS[@]}"; do
  k="${kv%%=*}"
  allowed "$k" || { echo "STOP: flag $k is not allowed"; exit 2; }
  case "$kv" in *=*) ;; *) echo "STOP: $kv needs NAME=VALUE"; exit 2 ;; esac
done

mkdir -p "$REPORT_DIR"
[ -f "$BAK" ] || { cp "$ENV" "$BAK"; chmod 600 "$BAK"; }

TMP=$(mktemp)
{
  echo "# File: $REPORT"
  echo "# Rollout report (A42), generated $(date -u +%Y-%m-%dT%H:%MZ)"
  echo
  echo "Replay report used: \`$REPLAY\`. Backup of \`.env\` before the run: \`$BAK\`."
  echo "p95 latency and a multi-photo live replay are NOT measured by this script."
  echo
  echo "| Flag | Value | Result | MemAvail before/after MB | /health/deep | classify (HTTP, s) | journal errors | Rollback |"
  echo "|---|---|---|---|---|---|---|---|"
} >"$TMP"

LIVE=(); OFF=()
for kv in "${FLAGS[@]}"; do
  k="${kv%%=*}"; v="${kv#*=}"
  had=0; old=""
  if has_kv "$k"; then had=1; old=$(get_kv "$k"); fi
  m0=$(mem)
  if [ "$m0" -lt "$MIN_MEM" ]; then
    echo "SKIP $k: MemAvailable $m0 MB under $MIN_MEM"
    echo "| $k | $v | SKIPPED (low RAM) | $m0/- | - | - | - | - |" >>"$TMP"
    OFF+=("$k=$v (low RAM)"); continue
  fi
  echo "== $k=$v"
  start=$(date -u +"%Y-%m-%d %H:%M:%S")
  set_kv "$k" "$v"
  restart
  ok=1; deep="-"; cls="-"; errs="-"
  if ! wait_up; then ok=0; deep="health down"; fi
  if [ "$ok" = 1 ]; then
    code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/health/deep")
    deep="$code"; [ "$code" = 200 ] || ok=0
  fi
  if [ "$ok" = 1 ] && [ -n "$PHOTO" ]; then
    out=$(curl -s -o /dev/null -w '%{http_code} %{time_total}' -F "image=@$PHOTO" "$BASE/classify?lang=en")
    cls="${out// /, }"; [ "${out%% *}" = 200 ] || ok=0
  fi
  if [ "$ok" = 1 ]; then
    errs=$(sudo journalctl -u wasteai --since "$start" -o cat 2>/dev/null | grep -ciE 'traceback|"level": *"error"')
    [ "${errs:-0}" -eq 0 ] || ok=0
  fi
  m1=$(mem)
  [ "$m1" -ge "$MIN_MEM" ] || ok=0
  if [ "$ok" = 1 ]; then
    res=LIVE; LIVE+=("$k=$v")
    rb="set $k=${old:-<unset>} (or remove line), restart wasteai"
    [ "$had" = 1 ] || rb="remove the $k line from .env, restart wasteai"
  else
    res="REVERTED"; OFF+=("$k=$v (check failed)")
    if [ "$had" = 1 ]; then set_kv "$k" "$old"; else del_kv "$k"; fi
    restart; wait_up || echo "WARNING: /health not up after revert of $k"
    rb="already reverted"
  fi
  echo "   $res  mem $m0 -> $m1 MB, deep=$deep, classify=$cls, errors=$errs"
  echo "| $k | $v | $res | $m0/$m1 | $deep | $cls | $errs | $rb |" >>"$TMP"
done

echo "-- ownership check (must be 0)"
bash deploy/install.sh --fix-owner | tail -n 2
st=$(bash deploy/install.sh --status 2>&1 | tail -n 5)

{
  echo
  echo "## Flags live"
  if [ "${#LIVE[@]}" -gt 0 ]; then for x in "${LIVE[@]}"; do echo "- $x"; done; else echo "- none"; fi
  echo
  echo "## Flags off, with reason"
  if [ "${#OFF[@]}" -gt 0 ]; then for x in "${OFF[@]}"; do echo "- $x"; done; else echo "- none"; fi
  echo
  echo "## Rollback"
  echo "- All flags: \`bash scripts/rollout_a42.sh --rollback\` (restores the pre-run .env, restarts only wasteai)."
  echo "- One flag: see the Rollback column above."
  echo
  echo "## NOT run by this script"
  echo "- \`scripts/parity_check.sh\`, the \`afpl-tactics\` site check, p95 over many photos, \`scripts/replay.py --live 20\`."
  echo
  echo "## install.sh --status (tail)"
  echo '```'
  echo "$st"
  echo '```'
} >>"$TMP"

mv "$TMP" "$REPORT"
echo "report written: $REPORT ($(wc -l <"$REPORT") lines)"
echo "next by hand: bash scripts/parity_check.sh --public-base https://wasteai.duckdns.org ; python3 scripts/replay.py --live 20"

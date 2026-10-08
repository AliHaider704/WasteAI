# File: scripts/sandbox_test.sh
#!/usr/bin/env bash
# A19: add systemd sandbox flags to wasteai.service ONE AT A TIME, keeping only flags that
# leave the service active with local_onnx up and /health/deep = 200 (real onnxruntime inference).
# Flags go in a drop-in (survives install.sh, which rewrites only the main unit).
# Usage: sudo -v; bash scripts/sandbox_test.sh [--status|--rollback] [/path/photo.jpg]
set -u
UNIT=wasteai.service
APP=${APP:-/home/ubuntu/waste_ai}
PORT=${PORT:-8100}
DIR=/etc/systemd/system/wasteai.service.d
DROP=$DIR/sandbox.conf
BASE="http://127.0.0.1:$PORT/api/v1"

log() { echo "[a19] $*"; }
rollback() {
  sudo rm -f "$DROP"; sudo rmdir "$DIR" 2>/dev/null || true
  sudo systemctl daemon-reload; sudo systemctl restart "$UNIT"
  log "rolled back: drop-in removed, service $(systemctl is-active $UNIT)"
}
case "${1:-}" in
  --rollback) rollback; exit 0 ;;
  --status)
    [ -f "$DROP" ] && cat "$DROP" || log "no sandbox drop-in"
    systemd-analyze security "$UNIT" --no-pager 2>/dev/null | tail -1; exit 0 ;;
esac
PHOTO=${1:-}

healthy() {  # service active, local_onnx up, deep check 200
  local i
  for i in $(seq 1 25); do
    systemctl is-active --quiet "$UNIT" && curl -fs "$BASE/health" 2>/dev/null | grep -q '"local_onnx":"up"' && break
    sleep 1
  done
  systemctl is-active --quiet "$UNIT" || return 1
  curl -fs "$BASE/health" | grep -q '"local_onnx":"up"' || return 1
  [ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/health/deep")" = "200" ] || return 1
  if [ -n "$PHOTO" ] && [ -f "$PHOTO" ]; then
    [ "$(curl -s -o /dev/null -w '%{http_code}' -F "image=@$PHOTO" "$BASE/classify?lang=en")" = "200" ] || return 1
  fi
  return 0
}

apply() {  # args: flag lines
  sudo mkdir -p "$DIR"
  { echo "[Service]"; printf '%s\n' "$@"; } | sudo tee "$DROP" >/dev/null
  sudo systemctl daemon-reload
  sudo systemctl restart "$UNIT"
}

FLAGS=(
  "ProtectSystem=strict"
  "ReadWritePaths=$APP/server/data"
  "ProtectHome=read-only"
  "PrivateDevices=true"
  "ProtectKernelTunables=true"
  "ProtectKernelModules=true"
  "ProtectKernelLogs=true"
  "ProtectControlGroups=true"
  "ProtectClock=true"
  "ProtectHostname=true"
  "LockPersonality=true"
  "RestrictRealtime=true"
  "RestrictSUIDSGID=true"
  "RestrictNamespaces=true"
  "RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX"
  "CapabilityBoundingSet="
  "SystemCallArchitectures=native"
  "SystemCallFilter=@system-service"
  "MemoryDenyWriteExecute=true"
)

healthy || { log "baseline NOT healthy, fix the service first"; exit 1; }
log "baseline: $(systemd-analyze security "$UNIT" --no-pager 2>/dev/null | tail -1)"

ACC=(); REJ=()
for f in "${FLAGS[@]}"; do
  apply "${ACC[@]}" "$f"
  if healthy; then ACC+=("$f"); log "OK   $f"
  else REJ+=("$f"); log "FAIL $f ($(sudo journalctl -u "$UNIT" -n 3 --no-pager -o cat 2>/dev/null | tail -1 | cut -c1-120))"; fi
done

if [ ${#ACC[@]} -eq 0 ]; then rollback; else apply "${ACC[@]}"; healthy || { log "final state unhealthy"; rollback; exit 1; }; fi
log "kept    : ${ACC[*]:-none}"
log "rejected: ${REJ[*]:-none}"
log "score   : $(systemd-analyze security "$UNIT" --no-pager 2>/dev/null | tail -1)"
log "free    : $(free -m | awk '/Mem:/{print $7" MB available"}')"
log "rollback: bash scripts/sandbox_test.sh --rollback"

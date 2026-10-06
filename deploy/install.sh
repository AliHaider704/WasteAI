# deploy/install.sh
#!/usr/bin/env bash
# Idempotent installer for wasteai on the shared EC2 host. No Docker. Never restarts nginx/docker/afplbot.
# Usage: bash deploy/install.sh --domain <SUBDOMAIN> [--email you@x.com]
#        bash deploy/install.sh --status | --rollback | --fix-owner | --stop-containers
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP=/home/ubuntu/waste_ai
STATE_DIR=/var/lib/wasteai
STATE="$STATE_DIR/state.txt"
UNIT=wasteai.service
UNIT_DST="/etc/systemd/system/$UNIT"
NGX_AV=/etc/nginx/sites-available/wasteai
NGX_EN=/etc/nginx/sites-enabled/wasteai
PORT=8100
DOMAIN="${WASTEAI_DOMAIN:-}"
EMAIL="${CERTBOT_EMAIL:-}"
ACTION=install

log() { printf '[wasteai] %s\n' "$*"; }
die() { printf '[wasteai] ERROR: %s\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --status) ACTION=status ;;
    --rollback) ACTION=rollback ;;
    --fix-owner) ACTION=fixowner ;;
    --stop-containers) ACTION=stopc ;;
    --domain) DOMAIN="${2:-}"; shift ;;
    --email) EMAIL="${2:-}"; shift ;;
    -h|--help) sed -n '3,5p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) die "unknown flag: $1" ;;
  esac
  shift
done

state_get() { sudo grep -s "^$1=" "$STATE" | tail -n1 | cut -d= -f2- || true; }
state_set() {
  local t; t="$(mktemp)"
  sudo grep -sv "^$1=" "$STATE" >"$t" || true
  echo "$1=$2" >>"$t"
  sudo install -d -m 755 "$STATE_DIR"
  sudo install -m 600 "$t" "$STATE"
  rm -f "$t"
}
env_get() { grep -s "^$1=" "$APP/server/.env" | tail -n1 | cut -d= -f2- | tr -d '"' || true; }
env_set() {
  local f="$APP/server/.env"
  if grep -q "^$1=" "$f"; then sed -i "s|^$1=.*|$1=$2|" "$f"; else echo "$1=$2" >>"$f"; fi
}
avail_mb() { free -m | awk '/^Mem:/{print $7}'; }

fix_owner() {
  local d n=0
  for d in "$REPO" "$APP"; do [ -d "$d" ] && sudo chown -R ubuntu:ubuntu "$d"; done
  for d in "$REPO" "$APP"; do
    [ -d "$d" ] && n=$((n + $(find "$d" ! -user ubuntu | wc -l)))
  done
  log "entries not owned by ubuntu: $n"
  [ "$n" -eq 0 ]
}

cmd_status() {
  log "service : $(systemctl is-active "$UNIT" 2>/dev/null || true)"
  log "nginx   : $( [ -e "$NGX_EN" ] && echo enabled || echo absent)"
  log "RAM avail (MB): $(avail_mb)"
  if curl -fsS --max-time 5 "http://127.0.0.1:$PORT/api/v1/health"; then echo; else log "local health: FAIL"; fi
  [ -f "$STATE" ] && sudo cat "$STATE" || log "no state file"
}

cmd_stop_containers() {
  local a
  read -r -p "Type STOP to run 'docker compose stop' in /home/ubuntu/AFPL_Bot: " a
  [ "$a" = "STOP" ] || die "not confirmed"
  (cd /home/ubuntu/AFPL_Bot && sudo docker compose stop)
  state_set containers_stopped "$(date -u +%FT%TZ)"
  log "containers stopped (no prune). Start again: cd /home/ubuntu/AFPL_Bot && sudo docker compose start"
}

cmd_rollback() {
  log "rolling back (app dir, .env, data and certificates are kept)"
  sudo systemctl disable --now "$UNIT" 2>/dev/null || true
  sudo rm -f "$UNIT_DST" "$NGX_EN" "$NGX_AV"
  sudo systemctl daemon-reload
  if sudo nginx -t; then sudo systemctl reload nginx; else die "nginx -t failed, check manually"; fi
  state_set rolled_back "$(date -u +%FT%TZ)"
  log "done. Full removal: sudo rm -rf $APP"
}

install_deps() {
  local miss=() p
  for p in python3 python3-venv python3-pip nginx certbot python3-certbot-nginx rsync curl acl; do
    dpkg -s "$p" >/dev/null 2>&1 || miss+=("$p")
  done
  if [ "${#miss[@]}" -gt 0 ]; then
    log "installing missing packages: ${miss[*]}"
    sudo apt-get update -qq
    sudo apt-get install -y --no-install-recommends "${miss[@]}"
  fi
}

sync_files() {
  install -d "$APP" "$APP/models"
  rsync -a --delete --exclude '.env' --exclude 'data/app.db*' --exclude '__pycache__' \
    --exclude '.pytest_cache' --exclude 'eval' --exclude 'tests' "$REPO/server/" "$APP/server/"
  rsync -a --delete "$REPO/frontend/" "$APP/frontend/"
  rsync -a --delete "$REPO/content/" "$APP/content/"
  rsync -a --delete "$REPO/contract/" "$APP/contract/"
  # nginx (www-data) must read the static files under /home/ubuntu
  sudo setfacl -m u:www-data:x /home/ubuntu
  chmod -R o+rX "$APP/frontend"
}

setup_venv() {
  [ -x "$APP/.venv/bin/python" ] || python3 -m venv "$APP/.venv"
  local h; h="$(sha256sum "$APP/server/requirements.txt" | cut -d' ' -f1)"
  if [ "$(state_get req_hash)" != "$h" ]; then
    "$APP/.venv/bin/pip" install -q --no-cache-dir -r "$APP/server/requirements.txt"
    state_set req_hash "$h"
  fi
}

setup_env() {
  local f="$APP/server/.env"
  if [ ! -f "$f" ]; then
    cp "$REPO/server/.env.example" "$f"
    log "created $f from .env.example (add AZURE_VISION_KEY there if you have one)"
  fi
  chmod 600 "$f"
  [ -n "$(env_get MODEL_PATH)" ] || env_set MODEL_PATH "$APP/models/model.onnx"
  [ -n "$(env_get MODEL_LABELS_PATH)" ] || env_set MODEL_LABELS_PATH "$APP/server/data/model_labels.json"
}

fetch_model() {
  local url sha path t got
  url="$(env_get MODEL_URL)"; sha="$(env_get MODEL_SHA256)"; path="$(env_get MODEL_PATH)"
  if [ -f "$path" ] && { [ -z "$sha" ] || [ "$(sha256sum "$path" | cut -d' ' -f1)" = "$sha" ]; }; then
    log "model present"; return 0
  fi
  if [ -z "$url" ]; then log "WARNING: MODEL_URL empty, local_onnx stays down"; return 0; fi
  t="$(mktemp)"
  curl -fL --retry 3 -o "$t" "$url" || { rm -f "$t"; die "model download failed"; }
  got="$(sha256sum "$t" | cut -d' ' -f1)"
  if [ -n "$sha" ] && [ "$got" != "$sha" ]; then rm -f "$t"; die "model SHA256 mismatch"; fi
  [ -n "$sha" ] || log "WARNING: MODEL_SHA256 empty, not verified"
  install -m 644 "$t" "$path"; rm -f "$t"
}

install_unit() {
  local t; t="$(mktemp)"
  sed "s|__APP__|$APP|g;s|__PORT__|$PORT|g" "$REPO/deploy/templates/wasteai.service" >"$t"
  if ! sudo cmp -s "$t" "$UNIT_DST"; then
    sudo install -m 644 "$t" "$UNIT_DST"
    sudo systemctl daemon-reload
    state_set unit_installed "$(date -u +%FT%TZ)"
  fi
  rm -f "$t"
  sudo systemctl enable "$UNIT" >/dev/null 2>&1
  sudo systemctl restart "$UNIT"   # our own service only
}

install_nginx() {
  if [ -f "$NGX_AV" ] && sudo grep -q 'managed by Certbot' "$NGX_AV"; then
    log "nginx block already managed by Certbot, left unchanged"; return 0
  fi
  local t; t="$(mktemp)"
  sed "s|__DOMAIN__|$DOMAIN|g;s|__APP__|$APP|g;s|__PORT__|$PORT|g" "$REPO/deploy/templates/nginx.conf.tpl" >"$t"
  if ! sudo cmp -s "$t" "$NGX_AV"; then
    sudo install -m 644 "$t" "$NGX_AV"
    state_set nginx_installed "$(date -u +%FT%TZ)"
  fi
  rm -f "$t"
  sudo ln -sf "$NGX_AV" "$NGX_EN"
  if sudo nginx -t; then
    sudo systemctl reload nginx
  else
    sudo rm -f "$NGX_EN" "$NGX_AV"
    die "nginx -t failed; our block removed, nothing reloaded"
  fi
}

setup_certbot() {
  if sudo test -d "/etc/letsencrypt/live/$DOMAIN"; then log "certificate exists"; return 0; fi
  if [ -z "$EMAIL" ]; then log "WARNING: no --email, skipping certbot (camera needs HTTPS)"; return 0; fi
  sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" --redirect
}

health_check() {
  local i
  for i in 1 2 3 4 5 6; do
    curl -fsS --max-time 5 "http://127.0.0.1:$PORT/api/v1/health" >/dev/null && break
    sleep 2
  done
  curl -fsS --max-time 5 "http://127.0.0.1:$PORT/api/v1/health" || die "local health check failed: journalctl -u $UNIT -n 50"
  echo
  if sudo test -d "/etc/letsencrypt/live/$DOMAIN"; then
    curl -fsS --max-time 10 "https://$DOMAIN/api/v1/health" || die "HTTPS health check failed"
    echo
  fi
}

cmd_install() {
  [ "$(id -un)" = "ubuntu" ] || die "run as user ubuntu (uses sudo internally)"
  [ -n "$DOMAIN" ] || DOMAIN="$(state_get domain)"
  [ -n "$DOMAIN" ] || die "domain required: --domain <SUBDOMAIN> (D-012)"
  state_set domain "$DOMAIN"
  state_set ram_before_mb "$(avail_mb)"
  install_deps
  sync_files
  setup_venv
  setup_env
  fetch_model
  install_unit
  install_nginx
  setup_certbot
  health_check
  fix_owner || log "WARNING: ownership not clean, run --fix-owner"
  state_set ram_after_mb "$(avail_mb)"
  state_set last_install "$(date -u +%FT%TZ)"
  log "OK. RAM available MB before/after: $(state_get ram_before_mb) / $(state_get ram_after_mb)"
}

case "$ACTION" in
  status) cmd_status ;;
  rollback) cmd_rollback ;;
  fixowner) fix_owner ;;
  stopc) cmd_stop_containers ;;
  install) cmd_install ;;
esac

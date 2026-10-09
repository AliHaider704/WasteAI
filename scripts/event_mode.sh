# File: scripts/event_mode.sh
#!/usr/bin/env bash
# Event mode (A34, D-040): temporary higher /classify limit and a venue IP exempt from the fail2ban 429 jail.
#   bash scripts/event_mode.sh --status
#   sudo bash scripts/event_mode.sh --on --venue-ip <IP> --rate <N>
#   sudo bash scripts/event_mode.sh --off
# --on: saves old values, adds the IP to ignoreip of wasteai-429, sets RATE_CLASSIFY_PER_MIN=N in the app .env and
# the Nginx zone rate, reloads Nginx and fail2ban, restarts ONLY wasteai. --off restores the saved values.
# The venue IP is passed as an argument and kept only in the root-owned state file, never in the repo.
set -euo pipefail
STATE=/var/lib/wasteai/event_mode.txt
ENVF="${WASTEAI_ENV:-/home/ubuntu/waste_ai/server/.env}"
NGX=/etc/nginx/sites-available/wasteai
JAIL=/etc/fail2ban/jail.d/wasteai-429.local
MAXRATE=600

die() { echo "ERROR: $*" >&2; exit 1; }
need_root() { [ "$(id -u)" -eq 0 ] || die "run with sudo"; }
cur_env() { grep -s '^RATE_CLASSIFY_PER_MIN=' "$ENVF" | tail -n1 | cut -d= -f2- || true; }
cur_ngx() { grep -s -oE 'zone=wasteai:[0-9a-z]+ rate=[0-9]+r/m' "$NGX" | grep -oE 'rate=[0-9]+' | cut -d= -f2 || true; }
cur_ign() { grep -s '^ignoreip' "$JAIL" || true; }
avail() { awk '/MemAvailable/ {printf "%d", $2/1024}' /proc/meminfo; }

status() {
  if [ -f "$STATE" ]; then echo "event mode: ON (since $(grep '^since=' "$STATE" | cut -d= -f2))"; else echo "event mode: off"; fi
  echo "app rate (env): ${ENVF_RATE:-$(cur_env)} (empty = default 10)"
  echo "nginx rate: $(cur_ngx)r/m"
  echo "fail2ban ignoreip entries: $(cur_ign | wc -w | awk '{print $1-2}')"
  echo "wasteai: $(systemctl is-active wasteai 2>/dev/null || true); MemAvailable: $(avail) MB"
}

apply_rate() { # $1 = number or empty (remove line)
  if [ -z "$1" ]; then sed -i '/^RATE_CLASSIFY_PER_MIN=/d' "$ENVF"
  elif grep -q '^RATE_CLASSIFY_PER_MIN=' "$ENVF"; then sed -i "s|^RATE_CLASSIFY_PER_MIN=.*|RATE_CLASSIFY_PER_MIN=$1|" "$ENVF"
  else echo "RATE_CLASSIFY_PER_MIN=$1" >>"$ENVF"; fi
  sed -i -E "s|(zone=wasteai:[0-9a-z]+ rate=)[0-9]+(r/m)|\1${1:-10}\2|" "$NGX"
}

reload_all() {
  nginx -t >/dev/null 2>&1 || die "nginx -t failed; nothing reloaded (check $NGX)"
  systemctl reload nginx
  fail2ban-client reload >/dev/null 2>&1 || echo "WARN: fail2ban reload failed (is it installed?)"
  systemctl restart wasteai
  chown -h ubuntu:ubuntu "$ENVF" 2>/dev/null || true
}

on() {
  need_root
  local ip="" rate=""
  while [ $# -gt 0 ]; do case "$1" in
    --venue-ip) ip="${2:-}"; shift 2 ;; --rate) rate="${2:-}"; shift 2 ;; *) die "unknown flag $1" ;; esac; done
  [[ "$ip" =~ ^[0-9a-fA-F:.]+(/[0-9]+)?$ ]] || die "--venue-ip needs an IPv4/IPv6 address or CIDR"
  [[ "$rate" =~ ^[0-9]+$ ]] && [ "$rate" -ge 10 ] && [ "$rate" -le "$MAXRATE" ] || die "--rate must be 10..$MAXRATE"
  [ -f "$STATE" ] && die "event mode already on; run --off first"
  [ -f "$JAIL" ] || echo "WARN: no fail2ban jail file; only the rate limits change"
  [ -f "$NGX" ] || die "$NGX not found"
  umask 077
  {
    echo "since=$(date -u +%FT%TZ)"
    echo "env_rate=$(cur_env)"
    echo "ngx_rate=$(cur_ngx)"
    echo "ignoreip_line=$(cur_ign)"
  } >"$STATE"
  [ -f "$JAIL" ] && sed -i -E "s|^(ignoreip *=.*)$|\1 $ip|" "$JAIL"
  apply_rate "$rate"
  reload_all
  echo "event mode ON: rate $rate/min, venue IP exempt from the 429 jail. Remember: --off after the event."
  status
}

off() {
  need_root
  [ -f "$STATE" ] || { echo "event mode is not on; nothing to restore"; status; return 0; }
  local env_rate ngx_rate line
  env_rate="$(grep '^env_rate=' "$STATE" | cut -d= -f2-)"
  ngx_rate="$(grep '^ngx_rate=' "$STATE" | cut -d= -f2-)"
  line="$(grep '^ignoreip_line=' "$STATE" | cut -d= -f2-)"
  if [ -f "$JAIL" ] && [ -n "$line" ]; then
    esc="$(printf '%s' "$line" | sed -e 's/[\\|&]/\\&/g')"
    sed -i -E "s|^ignoreip *=.*$|$esc|" "$JAIL"
  fi
  apply_rate "$env_rate"
  [ -n "$ngx_rate" ] && sed -i -E "s|(zone=wasteai:[0-9a-z]+ rate=)[0-9]+(r/m)|\1${ngx_rate}\2|" "$NGX"
  rm -f "$STATE"
  reload_all
  echo "event mode OFF: previous values restored"
  status
}

case "${1:-}" in
  --status) status ;;
  --on) shift; on "$@" ;;
  --off) off ;;
  *) sed -n '3,9p' "${BASH_SOURCE[0]}"; exit 2 ;;
esac

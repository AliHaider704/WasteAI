# File: scripts/host_hardening.sh
#!/usr/bin/env bash
# A18: host hardening. Default = read-only check (PASS/WARN/FAIL).
#   sudo bash scripts/host_hardening.sh                      check only
#   sudo bash scripts/host_hardening.sh --install-fail2ban   install jail if RAM allows
#   sudo bash scripts/host_hardening.sh --rollback           remove jail, disable fail2ban
# Never touches ufw rules, sshd config, docker or the afpl units. Never restarts nginx.
set -u
MIN_MB=300
JAIL=/etc/fail2ban/jail.d/wasteai-429.local
FILT=/etc/fail2ban/filter.d/wasteai-429.conf
LOG=/var/log/nginx/access.log
FAIL=0

say() { printf '%-5s %s\n' "$1" "$2"; if [ "$1" = FAIL ]; then FAIL=$((FAIL + 1)); fi; return 0; }
avail() { awk '/MemAvailable/ {printf "%d", $2/1024}' /proc/meminfo; }
[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 2; }

rollback() {
  rm -f "$JAIL" "$FILT"
  systemctl disable --now fail2ban >/dev/null 2>&1
  echo "fail2ban jail removed and service disabled (package kept). RAM available: $(avail) MB"
}

install_f2b() {
  local before after
  before=$(avail)
  if [ "$before" -lt "$MIN_MB" ]; then
    echo "SKIP: MemAvailable ${before} MB < ${MIN_MB} MB. Use Nginx limit_req only (D-032)."; exit 0
  fi
  command -v fail2ban-client >/dev/null 2>&1 || apt-get install -y fail2ban >/dev/null || { echo "apt failed"; exit 1; }
  cat > "$FILT" <<'EOF'
[Definition]
failregex = ^<HOST> -.*"[A-Z]+ /api/[^"]*" 429 
ignoreregex =
EOF
  cat > "$JAIL" <<EOF
[wasteai-429]
enabled  = true
filter   = wasteai-429
logpath  = $LOG
port     = http,https
maxretry = 5
findtime = 60
bantime  = 3600
ignoreip = 127.0.0.1/8 ::1 $(curl -s --max-time 5 https://checkip.amazonaws.com)
EOF
  fail2ban-client -t >/dev/null 2>&1 || { echo "fail2ban config test failed, rolling back"; rollback; exit 1; }
  systemctl enable --now fail2ban >/dev/null 2>&1
  systemctl reload fail2ban >/dev/null 2>&1
  sleep 5
  after=$(avail)
  echo "RAM available before/after: ${before}/${after} MB"
  if [ "$after" -lt "$MIN_MB" ]; then
    echo "MemAvailable below ${MIN_MB} MB, rolling back"; rollback; exit 1
  fi
  fail2ban-client status wasteai-429 || true
}

check() {
  local m; m=$(avail)
  if [ "$m" -ge "$MIN_MB" ]; then say PASS "MemAvailable ${m} MB (>= ${MIN_MB})"; else say WARN "MemAvailable ${m} MB (< ${MIN_MB}): no fail2ban"; fi

  # ufw (documented check only; the AWS Security Group is the real firewall)
  if command -v ufw >/dev/null 2>&1; then
    if ufw status 2>/dev/null | grep -q "Status: active"; then say PASS "ufw active"; else say WARN "ufw inactive (AWS Security Group must allow only 22/80/443; Docker ports bypass ufw)"; fi
  else say WARN "ufw not installed (rely on the AWS Security Group)"; fi

  # public listeners other than 22/80/443
  local extra
  extra=$(ss -H -ltn 2>/dev/null | awk '{print $4}' | grep -Ev '^(127\.|\[::1\]|::1)' | grep -Ev ':(22|80|443)$' | sort -u | tr '\n' ' ')
  if [ -z "$extra" ]; then say PASS "no extra public listeners"; else say WARN "listening on non-loopback: ${extra}(must be closed by the Security Group)"; fi
  if ss -H -ltn 2>/dev/null | awk '{print $4}' | grep -q '^127.0.0.1:8100$'; then say PASS "wasteai bound to 127.0.0.1:8100"; else say FAIL "127.0.0.1:8100 not listening"; fi

  # sshd effective config
  if command -v sshd >/dev/null 2>&1; then
    local cfg; cfg=$(sshd -T 2>/dev/null)
    echo "$cfg" | grep -qi '^passwordauthentication no' && say PASS "ssh PasswordAuthentication no" || say WARN "ssh PasswordAuthentication is not 'no'"
    echo "$cfg" | grep -Eqi '^permitrootlogin (no|prohibit-password|without-password)' && say PASS "ssh root login restricted" || say WARN "ssh root login allowed"
    echo "$cfg" | grep -qi '^pubkeyauthentication yes' && say PASS "ssh pubkey on" || say WARN "ssh pubkey off"
  else say WARN "sshd not found"; fi

  # automatic security patches (W-02)
  if dpkg -s unattended-upgrades >/dev/null 2>&1; then
    if grep -rqs 'Unattended-Upgrade "1"' /etc/apt/apt.conf.d/; then say PASS "unattended-upgrades enabled"; else say WARN "unattended-upgrades installed but not enabled"; fi
  else say WARN "unattended-upgrades not installed"; fi

  # fail2ban jail
  if command -v fail2ban-client >/dev/null 2>&1 && systemctl is-active --quiet fail2ban; then
    fail2ban-client status wasteai-429 >/dev/null 2>&1 && say PASS "fail2ban jail wasteai-429 active" || say WARN "fail2ban running without wasteai-429 jail"
  else say WARN "fail2ban not running (optional; Nginx limit_req still applies)"; fi

  # services that must stay up
  for u in nginx wasteai; do systemctl is-active --quiet "$u" && say PASS "$u active" || say FAIL "$u not active"; done
  nginx -t >/dev/null 2>&1 && say PASS "nginx -t" || say FAIL "nginx -t"
  [ -f "$LOG" ] && say PASS "nginx access log present ($(grep -c ' 429 ' "$LOG" 2>/dev/null) lines with 429)" || say WARN "$LOG missing (jail would not work)"
  echo "done: ${FAIL} FAIL"
  [ "$FAIL" -eq 0 ]
}

case "${1:-}" in
  --install-fail2ban) install_f2b ;;
  --rollback) rollback ;;
  "") check ;;
  *) echo "usage: $0 [--install-fail2ban|--rollback]"; exit 2 ;;
esac

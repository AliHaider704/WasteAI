# File: scripts/load_probe.sh
#!/usr/bin/env bash
# Bounded load probe against the OWN host only (A34). Sends N small generated noise images to /classify,
# waits a fixed pause between requests, prints HTTP code counts, MemAvailable before/after, median and p95 time.
#   bash scripts/load_probe.sh --n 30 --pause 2 [--base http://127.0.0.1:8100] [--lang en]
# Hard caps: N <= 200, pause >= 0.2 s. Stops early if MemAvailable < 300 MB. Never touches another host.
# Note: images are random noise, so every request is a cache miss and runs the real sources (Azure quota is used).
set -euo pipefail
N=20; PAUSE=2; BASE=http://127.0.0.1:8100; LANGP=en
while [ $# -gt 0 ]; do case "$1" in
  --n) N="$2"; shift 2 ;; --pause) PAUSE="$2"; shift 2 ;; --base) BASE="$2"; shift 2 ;; --lang) LANGP="$2"; shift 2 ;;
  *) echo "unknown flag $1" >&2; exit 2 ;; esac; done
[[ "$N" =~ ^[0-9]+$ ]] && [ "$N" -ge 1 ] && [ "$N" -le 200 ] || { echo "--n must be 1..200" >&2; exit 2; }
awk -v p="$PAUSE" 'BEGIN{exit !(p+0>=0.2)}' || { echo "--pause must be >= 0.2" >&2; exit 2; }
host="${BASE#*://}"; host="${host%%[:/]*}"
own=""; [ -r /var/lib/wasteai/state.txt ] && own="$(sudo -n grep '^domain=' /var/lib/wasteai/state.txt 2>/dev/null | cut -d= -f2 || true)"
case "$host" in 127.0.0.1|localhost) ;; *) [ -n "$own" ] && [ "$host" = "$own" ] || { echo "refusing: --base must be this host (127.0.0.1, localhost or its own domain)" >&2; exit 2; } ;; esac
avail() { awk '/MemAvailable/ {printf "%d", $2/1024}' /proc/meminfo; }
before="$(avail)"; tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
codes=(); times=()
for i in $(seq 1 "$N"); do
  [ "$(avail)" -ge 300 ] || { echo "STOP: MemAvailable under 300 MB at request $i"; break; }
  python3 - "$tmp/p.png" "$i" <<'PY'
import os, struct, sys, zlib
w = h = 96
raw = b"".join(b"\x00" + os.urandom(w * 3) for _ in range(h))
def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
open(sys.argv[1], "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                              + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
PY
  out="$(curl -s -o /dev/null -w '%{http_code} %{time_total}' --max-time 20 -F "image=@$tmp/p.png;type=image/png" "$BASE/api/v1/classify?lang=$LANGP" || echo '000 20')"
  codes+=("${out% *}"); times+=("${out#* }")
  sleep "$PAUSE"
done
after="$(avail)"
echo "codes: $(printf '%s\n' "${codes[@]}" | sort | uniq -c | awk '{printf "%s x%s  ", $2, $1}')"
echo "MemAvailable before/after: ${before}/${after} MB"
printf '%s\n' "${times[@]}" | sort -n | awk '{a[NR]=$1} END{ if(!NR) exit; m=(NR%2)?a[(NR+1)/2]:(a[NR/2]+a[NR/2+1])/2; p=a[int(NR*0.95+0.999)];
  printf "time median %.3f s, p95 %.3f s over %d requests\n", m, p, NR}'
s503=$(printf '%s\n' "${codes[@]}" | grep -c '^503$' || true)
echo "share of 503: $s503/${#codes[@]}"

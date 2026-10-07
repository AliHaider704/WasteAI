# File: scripts/a3_measure.sh
#!/usr/bin/env bash
# A3: check local_onnx is up, measure service memory and per-photo latency.
# Usage: bash scripts/a3_measure.sh [--base URL] [--photo FILE] [--n 12]
set -u
BASE="https://wasteai.duckdns.org"; PHOTO=""; N=12
while [ $# -gt 0 ]; do
  case "$1" in
    --base) BASE="$2"; shift 2 ;;
    --photo) PHOTO="$2"; shift 2 ;;
    --n) N="$2"; shift 2 ;;
    *) echo "unknown flag $1"; exit 2 ;;
  esac
done

echo "== health"
H="$(curl -fsS "$BASE/api/v1/health")" || { echo "FAIL: health unreachable"; exit 1; }
echo "$H"
case "$H" in *'"local_onnx":"up"'*) echo "PASS: local_onnx up" ;; *) echo "FAIL: local_onnx not up (check MODEL_URL, active label set, journalctl -u wasteai -n 30)"; exit 1 ;; esac

echo "== memory (systemd)"
systemctl show wasteai -p MemoryCurrent -p MemoryPeak -p MemoryHigh -p MemoryMax
PID="$(systemctl show wasteai -p MainPID --value)"
[ -n "$PID" ] && [ "$PID" != "0" ] && grep -E "VmRSS|VmHWM" "/proc/$PID/status"
echo "== host"; free -m | sed -n '1,2p'

if [ -z "$PHOTO" ]; then echo "(no --photo: latency skipped)"; exit 0; fi
[ -f "$PHOTO" ] || { echo "FAIL: photo not found"; exit 1; }

echo "== latency ($N calls, 7 s apart for the 10/min limit; cache is hit after the first, so a fresh copy is sent each time)"
T="$(mktemp)"; : >"$T"
for i in $(seq 1 "$N"); do
  C="$(mktemp --suffix=.jpg)"; cp "$PHOTO" "$C"; printf '\0' >>"$C"   # new hash each call, bypasses cache
  R="$(curl -s -o /tmp/a3_resp.json -w '%{http_code} %{time_total}' -F "image=@$C" "$BASE/api/v1/classify?lang=en")"
  rm -f "$C"
  echo "call $i: $R"
  echo "$R" | awk '$1==200{print $2}' >>"$T"
  sleep 7
done
echo "== sources in last response"; python3 - <<'E'
import json
d=json.load(open("/tmp/a3_resp.json"))
for s in d.get("sources",[]): print(s["name"], s["ok"], s.get("top"))
print("elapsed_ms", d.get("elapsed_ms"))
E
echo "== summary (HTTP 200 only, seconds)"
sort -n "$T" | awk '{a[NR]=$1} END{if(!NR){print "no 200 responses";exit}
  printf "n=%d median=%.3f p95=%.3f max=%.3f\n",NR,a[int((NR+1)/2)],a[int(NR*0.95+0.5)>NR?NR:int(NR*0.95+0.5)],a[NR]}'
rm -f "$T"
echo "== memory after load"
systemctl show wasteai -p MemoryCurrent -p MemoryPeak
echo "RULE: if MemoryCurrent > 80% of MemoryHigh (350M), record it and mark D-018 option A+ not feasible."

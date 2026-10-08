# File: scripts/ops_a21.py
"""A21 supply chain and ops helper (stdlib only, run as user ubuntu, not as root).

  python3 scripts/ops_a21.py audit    [--req server/requirements.txt]
  python3 scripts/ops_a21.py backup   [--db PATH] [--dest DIR] [--keep-days 14]
  python3 scripts/ops_a21.py summary  [--days 7] [--out FILE]
  python3 scripts/ops_a21.py cron     (prints the crontab lines, installs nothing)

audit:   runs pip-audit in a throw-away venv (/tmp), so the app venv gains no package.
backup:  consistent copy through the SQLite backup API, gzip, mode 600, prune old files.
summary: counts events from the JSON journal lines of wasteai (no IPs are logged there).
"""
import argparse
import gzip
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timedelta

APP = "/home/ubuntu/waste_ai"
AUDIT_VENV = "/tmp/wasteai-audit-venv"


def cmd_audit(a):
    py = os.path.join(AUDIT_VENV, "bin", "python")
    if not os.path.exists(py):
        subprocess.run([sys.executable, "-m", "venv", AUDIT_VENV], check=True)
    if subprocess.run([py, "-m", "pip_audit", "--version"], capture_output=True).returncode != 0:
        subprocess.run([py, "-m", "pip", "install", "-q", "pip-audit"], check=True)
    r = subprocess.run([py, "-m", "pip_audit", "-r", a.req, "--progress-spinner", "off"])
    print("AUDIT", "OK: no known vulnerabilities" if r.returncode == 0 else "FINDINGS: see above")
    return r.returncode


def cmd_backup(a):
    if not os.path.exists(a.db):
        print("FAIL: database not found:", a.db)
        return 1
    os.makedirs(a.dest, mode=0o700, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    tmp = os.path.join(a.dest, f"app-{stamp}.db")
    out = tmp + ".gz"
    src = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    dst = sqlite3.connect(tmp)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    chk = sqlite3.connect(tmp)
    ok = chk.execute("PRAGMA integrity_check").fetchone()[0]
    chk.close()
    if ok != "ok":
        os.remove(tmp)
        print("FAIL: integrity_check:", ok)
        return 1
    with open(tmp, "rb") as f, gzip.open(out, "wb") as g:
        shutil.copyfileobj(f, g)
    os.remove(tmp)
    os.chmod(out, 0o600)
    cutoff = time.time() - a.keep_days * 86400
    pruned = 0
    for n in os.listdir(a.dest):
        p = os.path.join(a.dest, n)
        if n.startswith("app-") and n.endswith(".db.gz") and os.path.getmtime(p) < cutoff:
            os.remove(p)
            pruned += 1
    print(f"OK backup {out} ({os.path.getsize(out)} bytes), pruned {pruned}")
    print("Off-box copy is manual: scp this file to another machine regularly.")
    return 0


def _p95(v):
    v = sorted(v)
    return v[min(len(v) - 1, int(len(v) * 0.95))] if v else 0


def cmd_summary(a):
    since = (datetime.now() - timedelta(days=a.days)).strftime("%Y-%m-%d %H:%M:%S")
    r = subprocess.run(["journalctl", "-u", "wasteai", "--since", since, "-o", "cat", "--no-pager"],
                       capture_output=True, text=True)
    events, status, errs, lat = Counter(), Counter(), Counter(), []
    bad = 0
    for line in r.stdout.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            bad += 1
            continue
        events[d.get("event", "?")] += 1
        if d.get("event") == "request":
            status[(d.get("route", "?"), d.get("status"))] += 1
            if "classify" in str(d.get("route")) and isinstance(d.get("elapsed_ms"), (int, float)):
                lat.append(d["elapsed_ms"])
        if d.get("level") in ("error", "warning", "ERROR", "WARNING"):
            errs[d.get("event", "?")] += 1
    lines = [f"WasteAI weekly summary, last {a.days} days (from {since})", ""]
    lines.append("Events: " + ", ".join(f"{k}={v}" for k, v in events.most_common(12)))
    lines.append("")
    lines.append("Route / status:")
    for (rt, st), n in sorted(status.items(), key=lambda x: -x[1])[:15]:
        lines.append(f"  {rt} {st}: {n}")
    n429 = sum(n for (_, st), n in status.items() if st == 429)
    lines.append(f"\n429 total: {n429}")
    lines.append(f"classify latency: n={len(lat)} p95={_p95(lat)} ms")
    lines.append("Warnings/errors by event: " + (", ".join(f"{k}={v}" for k, v in errs.most_common(10)) or "none"))
    lines.append(f"degraded events: {events.get('degraded', 0)}; unparsable lines: {bad}")
    text = "\n".join(lines)
    print(text)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        os.chmod(a.out, 0o600)
    return 0


def cmd_cron(a):
    s = f"{APP}/../WasteAI/scripts/ops_a21.py"
    print("# crontab -e (user ubuntu). Adjust the repo path if different.")
    print(f"30 2 * * * python3 /home/ubuntu/WasteAI/scripts/ops_a21.py backup >> {APP}/backups/backup.log 2>&1")
    print(f"0 8 * * 1 python3 /home/ubuntu/WasteAI/scripts/ops_a21.py summary --out {APP}/backups/weekly.txt")
    print("# monthly dependency audit:")
    print(f"0 9 1 * * python3 /home/ubuntu/WasteAI/scripts/ops_a21.py audit --req {APP}/server/requirements.txt >> {APP}/backups/audit.log 2>&1")
    del s
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("audit")
    s.add_argument("--req", default=f"{APP}/server/requirements.txt")
    s.set_defaults(fn=cmd_audit)
    s = sub.add_parser("backup")
    s.add_argument("--db", default=f"{APP}/server/data/app.db")
    s.add_argument("--dest", default=f"{APP}/backups")
    s.add_argument("--keep-days", type=int, default=14)
    s.set_defaults(fn=cmd_backup)
    s = sub.add_parser("summary")
    s.add_argument("--days", type=int, default=7)
    s.add_argument("--out", default="")
    s.set_defaults(fn=cmd_summary)
    s = sub.add_parser("cron")
    s.set_defaults(fn=cmd_cron)
    a = p.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())

# server/app/quota.py
import time

from app import db
from app.ratelimit import TokenBucket

LIMIT = 4800  # Azure F0 = 5,000/month; keep a safety margin
SOURCE = "azure"
_bucket = TokenBucket(20)  # Azure F0: 20 calls/min


def _period() -> str:
    return time.strftime("%Y-%m", time.gmtime())


def used() -> int:
    row = db.query_one("SELECT count FROM quota WHERE period=? AND source=?", (_period(), SOURCE))
    return int(row[0]) if row else 0


def exhausted() -> bool:
    return used() >= LIMIT


def try_acquire() -> bool:
    """Reserve one Azure call. False if monthly cap or per-minute bucket is hit."""
    if exhausted() or not _bucket.take():
        return False
    db.execute(
        "INSERT INTO quota(period, source, count) VALUES(?,?,1) "
        "ON CONFLICT(period, source) DO UPDATE SET count = count + 1",
        (_period(), SOURCE),
    )
    return True

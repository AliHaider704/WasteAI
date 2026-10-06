# server/app/db.py
import os
import sqlite3
import threading
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).resolve().parents[1] / "data" / "app.db"))
_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS quota (
  period TEXT NOT NULL, source TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (period, source));
CREATE TABLE IF NOT EXISTS feedback (
  request_id TEXT NOT NULL, correct_category_id TEXT NOT NULL, ts INTEGER NOT NULL);
"""


def _get() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.executescript(SCHEMA)
        _conn.commit()
    return _conn


def execute(sql: str, params: tuple = ()) -> None:
    with _lock:
        conn = _get()
        conn.execute(sql, params)
        conn.commit()


def query_one(sql: str, params: tuple = ()):
    with _lock:
        return _get().execute(sql, params).fetchone()

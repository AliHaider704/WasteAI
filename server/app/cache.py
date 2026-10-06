# server/app/cache.py
"""SQLite result cache: SHA-256 of resized image + lang, TTL 7 days, JSON only."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path

TTL_SECONDS = 7 * 24 * 3600
_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS result_cache("
    "key TEXT PRIMARY KEY, result TEXT NOT NULL, ts INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS feedback("
    "request_id TEXT NOT NULL, correct_category_id TEXT NOT NULL, ts INTEGER NOT NULL)",
)


def db_path() -> str:
    default = Path(__file__).resolve().parents[1] / "data" / "app.db"
    return os.getenv("DB_PATH", str(default))


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path(), timeout=5)
    for stmt in _SCHEMA:
        conn.execute(stmt)
    return conn


def make_key(resized_image: bytes, lang: str) -> str:
    return f"{hashlib.sha256(resized_image).hexdigest()}:{lang}"


def _get(key: str) -> dict | None:
    conn = connect()
    try:
        row = conn.execute(
            "SELECT result, ts FROM result_cache WHERE key=?", (key,)
        ).fetchone()
        if row is None:
            return None
        if time.time() - row[1] > TTL_SECONDS:
            conn.execute("DELETE FROM result_cache WHERE key=?", (key,))
            conn.commit()
            return None
        return json.loads(row[0])
    finally:
        conn.close()


def _put(key: str, result: dict) -> None:
    conn = connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO result_cache(key, result, ts) VALUES(?,?,?)",
            (key, json.dumps(result, ensure_ascii=False), int(time.time())),
        )
        conn.commit()
    finally:
        conn.close()


def _purge() -> int:
    conn = connect()
    try:
        cur = conn.execute(
            "DELETE FROM result_cache WHERE ts < ?", (int(time.time()) - TTL_SECONDS,)
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


async def get(key: str) -> dict | None:
    """Cached result or None. Caller must set a fresh request_id/elapsed_ms."""
    try:
        return await asyncio.to_thread(_get, key)
    except sqlite3.Error:
        return None


async def put(key: str, result: dict) -> None:
    """Store only status ok/uncertain results. Never store images."""
    try:
        await asyncio.to_thread(_put, key, result)
    except sqlite3.Error:
        pass


async def purge_expired() -> int:
    try:
        return await asyncio.to_thread(_purge)
    except sqlite3.Error:
        return 0

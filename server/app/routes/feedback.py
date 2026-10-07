# File: server/app/routes/feedback.py
"""POST /feedback: only ids the server issued (7 days), one per id, per-IP limit."""
from __future__ import annotations

import asyncio
import sqlite3
import time

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app import cache, catalog
from app.deps import client_ip
from app.errors import build_error
from app.ratelimit import feedback_limiter

router = APIRouter()


class FeedbackIn(BaseModel):
    request_id: str = Field(min_length=1, max_length=64)
    correct_category_id: str = Field(min_length=1, max_length=64)


def _insert(request_id: str, category_id: str) -> None:
    """Insert once per request_id; a duplicate is ignored (first answer wins)."""
    conn = cache.connect()
    try:
        conn.execute(
            "INSERT INTO feedback(request_id, correct_category_id, ts) "
            "SELECT ?,?,? WHERE NOT EXISTS (SELECT 1 FROM feedback WHERE request_id=?)",
            (request_id, category_id, int(time.time()), request_id),
        )
        conn.commit()
    finally:
        conn.close()


@router.post("/feedback", status_code=204)
async def post_feedback(request: Request, body: FeedbackIn, lang: str = "en") -> Response:
    lang = lang if lang in ("ar", "en") else "en"
    rid = body.request_id
    wait = feedback_limiter.check(client_ip(request))
    if wait:
        return build_error("rate_limited", lang, rid, {"Retry-After": str(wait)})
    if body.correct_category_id not in catalog.by_id("en"):
        return build_error("invalid_request", lang, rid)
    if not await cache.is_issued(rid):
        return build_error("invalid_request", lang, rid)
    try:
        await asyncio.to_thread(_insert, rid, body.correct_category_id)
    except sqlite3.Error:
        return build_error("internal_error", lang, rid)
    return Response(status_code=204)

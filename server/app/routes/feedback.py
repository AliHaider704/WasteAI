# File: server/app/routes/feedback.py
from __future__ import annotations

import asyncio
import sqlite3
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app import cache
from app.aggregator import GROUP_OF

router = APIRouter()


class FeedbackIn(BaseModel):
    request_id: str = Field(min_length=1, max_length=64)
    correct_category_id: str = Field(min_length=1, max_length=64)


def _insert(request_id: str, category_id: str) -> None:
    conn = cache.connect()
    try:
        conn.execute(
            "INSERT INTO feedback(request_id, correct_category_id, ts) VALUES(?,?,?)",
            (request_id, category_id, int(time.time())),
        )
        conn.commit()
    finally:
        conn.close()


@router.post("/feedback", status_code=204)
async def post_feedback(body: FeedbackIn) -> Response:
    if body.correct_category_id not in GROUP_OF:
        return JSONResponse(
            status_code=422,
            content={"error": {
                "code": "invalid_request",
                "message": "Unknown category id.",
                "request_id": body.request_id,
            }},
        )
    try:
        await asyncio.to_thread(_insert, body.request_id, body.correct_category_id)
    except sqlite3.Error:
        return JSONResponse(
            status_code=500,
            content={"error": {
                "code": "internal_error",
                "message": "Could not save feedback.",
                "request_id": body.request_id,
            }},
        )
    return Response(status_code=204)

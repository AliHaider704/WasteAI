# File: server/app/routes/log.py
"""POST /log: sink for client events. Own limiter, sanitized detail, no IP stored."""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.deps import client_ip
from app.errors import build_error
from app.logging_setup import clean
from app.ratelimit import IPLimiter

router = APIRouter()
CLIENT_LOG = logging.getLogger("wasteai.client")
log_limiter = IPLimiter(20, 60.0)
_LEVELS = {"debug": logging.INFO, "info": logging.INFO, "warning": logging.WARNING, "error": logging.WARNING}


class ClientLog(BaseModel):
    level: Literal["debug", "info", "warning", "error"]
    event: str = Field(pattern=r"^[a-z0-9_.]{1,64}$")
    request_id: str | None = Field(default=None, max_length=64)
    detail: str | None = Field(default=None, max_length=2000)


@router.post("/log", status_code=204)
async def post_log(request: Request, body: ClientLog, lang: str = "en") -> Response:
    lang = lang if lang in ("ar", "en") else "en"
    wait = log_limiter.check(client_ip(request))
    if wait:
        return build_error("rate_limited", lang, body.request_id or "", {"Retry-After": str(wait)})
    CLIENT_LOG.log(
        _LEVELS[body.level],
        "client_event",
        extra={
            "event": "client_event",
            "origin": "client",
            "client_level": body.level,
            "client_event": body.event,
            "request_id": clean(body.request_id, 64) if body.request_id else None,
            "detail": clean(body.detail, 200) if body.detail else None,
        },
    )
    return Response(status_code=204)

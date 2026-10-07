# File: server/app/deps.py
"""Shared FastAPI dependencies."""
from typing import Annotated, Literal

from fastapi import Query, Request

Lang = Annotated[Literal["ar", "en"], Query(description="Response language")]


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def client_ip(request: Request) -> str:
    """Client address for in-memory rate limiting only (never stored or logged)."""
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")

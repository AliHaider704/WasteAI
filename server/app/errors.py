# File: server/app/errors.py
"""Stable error codes; messages come from contract/errors.json (single source)."""
from __future__ import annotations

import json
from functools import lru_cache

from fastapi import Request
from fastapi.responses import JSONResponse

from app.catalog import CONTRACT_DIR

_FALLBACK = {
    "http": 500,
    "message": {"en": "Something went wrong on our side.", "ar": "حدث خطأ من جهتنا."},
}


@lru_cache(maxsize=1)
def _table() -> dict[str, dict]:
    try:
        raw = json.loads((CONTRACT_DIR / "errors.json").read_text("utf-8"))
        return {e["code"]: e for e in raw["errors"]}
    except (OSError, ValueError, KeyError):
        return {"internal_error": _FALLBACK}


def status_of(code: str) -> int:
    return int(_table().get(code, _table().get("internal_error", _FALLBACK))["http"])


class AppError(Exception):
    def __init__(self, code: str, headers: dict[str, str] | None = None):
        self.code = code
        self.headers = headers or {}


def build_error(
    code: str, lang: str = "en", rid: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    entry = _table().get(code) or _table().get("internal_error", _FALLBACK)
    msg = entry["message"]
    body = {"error": {"code": code if code in _table() else "internal_error",
                      "message": msg["ar"] if lang == "ar" else msg["en"],
                      "request_id": rid or ""}}
    return JSONResponse(body, status_code=int(entry["http"]), headers=headers)


def error_response(
    request: Request, code: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    lang = request.query_params.get("lang", "en")
    rid = getattr(request.state, "request_id", "")
    return build_error(code, lang if lang in ("ar", "en") else "en", rid, headers)

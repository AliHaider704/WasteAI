# File: server/app/logging_setup.py
"""Structured JSON logging: one line per record on stdout, English only.

Never logged: client IP, request body, image data, raw labels. Only the fields
in FIELDS are copied from a record, so nothing leaks through `extra` by accident.
"""
from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone

FIELDS = (
    "request_id", "route", "status", "elapsed_ms", "source_status",
    "origin", "client_level", "client_event", "detail",
)
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]+")


def clean(text: str, limit: int) -> str:
    """Replace control characters (incl. newlines) with a space and cut to `limit`."""
    return _CONTROL.sub(" ", text).strip()[:limit]


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: dict = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "event": getattr(record, "event", None) or "log",
        }
        for key in FIELDS:
            value = getattr(record, key, None)
            if value is not None:
                data[key] = value
        if not hasattr(record, "event"):
            data["message"] = clean(record.getMessage(), 300)
        if record.exc_info and record.exc_info[0] is not None:
            data["exc_type"] = record.exc_info[0].__name__
            data["exc"] = clean(self.formatException(record.exc_info), 1500)
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def setup_logging(level: str = "INFO") -> None:
    """Install the JSON handler on the root logger (idempotent) and silence uvicorn access lines."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "_wasteai", False):
            root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    handler._wasteai = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(level.upper() if level.upper() in logging.getLevelNamesMapping() else "INFO")
    for name in ("uvicorn", "uvicorn.error"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
    access = logging.getLogger("uvicorn.access")  # it prints client IPs behind the proxy
    access.handlers.clear()
    access.propagate = False
    access.disabled = True


def note_result(request, result: dict) -> None:
    """Remember which sources answered, for the access line (names and ok flags only)."""
    request.state.source_status = {
        str(s.get("name")): bool(s.get("ok")) for s in result.get("sources", []) if isinstance(s, dict)
    }

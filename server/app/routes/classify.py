# File: server/app/routes/classify.py
import uuid

from fastapi import APIRouter, File, Request, UploadFile

from app import concurrency, imaging  # ADAPTERS: imaging.prepare(raw)->bytes, concurrency.slot()
from app.errresp import error_response
from app.orchestrator import AllSourcesFailed, get_orchestrator
from app.ratelimit import ip_limiter

router = APIRouter()
MAX_BYTES = 2 * 1024 * 1024


def _client_ip(request: Request) -> str:
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")


@router.post("/classify")
async def classify(request: Request, image: UploadFile = File(...), lang: str = "en"):
    rid = str(uuid.uuid4())
    if lang not in ("ar", "en"):
        return error_response("invalid_request", 422, "en", rid)
    wait = ip_limiter.check(_client_ip(request))
    if wait:
        return error_response("rate_limited", 429, lang, rid, {"Retry-After": str(wait)})
    raw = await image.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        return error_response("image_too_large", 413, lang, rid)
    try:
        data = imaging.prepare(raw)
    except Exception as exc:
        return error_response(
            getattr(exc, "code", "invalid_image"), getattr(exc, "status", 400), lang, rid
        )
    del raw
    try:
        async with concurrency.limiter.slot():
            return await get_orchestrator(request.app).run(data, lang, rid)
    except AllSourcesFailed:
        return error_response("all_sources_failed", 502, lang, rid)
    except Exception as exc:
        if getattr(exc, "code", None) == "overloaded":
            return error_response("overloaded", 503, lang, rid, {"Retry-After": "2"})
        return error_response("internal_error", 500, lang, rid)
    finally:
        data.close()

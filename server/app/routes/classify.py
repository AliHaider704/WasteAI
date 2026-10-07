# File: server/app/routes/classify.py
import time
import uuid

from fastapi import APIRouter, File, Form, Request, UploadFile

from app import cache, concurrency, imaging
from app.deps import client_ip
from app.errors import build_error
from app.logging_setup import note_result
from app.orchestrator import AllSourcesFailed, get_orchestrator
from app.ratelimit import ip_limiter

router = APIRouter()
MAX_BYTES = 2 * 1024 * 1024


@router.post("/classify")
async def classify(request: Request, image: UploadFile = File(...), lang: str = "en",
                   allow_cloud_llm: int = Form(0)):
    rid = str(uuid.uuid4())
    request.state.request_id = rid
    if lang not in ("ar", "en"):
        return build_error("invalid_request", "en", rid)
    if allow_cloud_llm not in (0, 1):
        return build_error("invalid_request", lang, rid)
    wait = ip_limiter.check(client_ip(request))
    if wait:
        return build_error("rate_limited", lang, rid, {"Retry-After": str(wait)})
    raw = await image.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        return build_error("image_too_large", lang, rid)
    try:
        data = imaging.prepare(raw)
    except Exception as exc:
        return build_error(
            getattr(exc, "code", "invalid_image"), lang, rid
        )
    del raw
    t0 = time.perf_counter()
    orch = get_orchestrator(request.app)
    use_llm = allow_cloud_llm == 1 and orch.llm_active()
    key = cache.make_key(data.sha256.encode(), lang + ("|llm" if use_llm else ""))
    hit = await cache.get(key)
    if hit is not None:
        data.close()
        hit["request_id"] = rid
        hit["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
        await cache.record_issued(rid)
        note_result(request, hit)
        return hit
    try:
        async with concurrency.limiter.slot():
            result = await orch.run(data, lang, rid, use_llm)
        if result.get("status") in ("ok", "uncertain"):
            await cache.put(key, result)
            await cache.record_issued(rid)
        note_result(request, result)
        return result
    except AllSourcesFailed:
        return build_error("all_sources_failed", lang, rid)
    except Exception as exc:
        if getattr(exc, "code", None) == "overloaded":
            return build_error("overloaded", lang, rid, {"Retry-After": "2"})
        return build_error("internal_error", lang, rid)
    finally:
        data.close()

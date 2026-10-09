# File: server/app/routes/health.py
import json
import time

from fastapi import APIRouter, Request, Response

from app.orchestrator import get_orchestrator

router = APIRouter()
LOOPBACK = {"127.0.0.1", "::1"}
CACHE_SECONDS = 5.0
_cache: dict = {"at": 0.0, "body": None}


def clear_cache() -> None:
    _cache["at"], _cache["body"] = 0.0, None


# GET and HEAD: a monitor that sends HEAD used to get 422 (405 mapped to invalid_request).
# Public shape unchanged; the answer is reused for 5 s so polling never recomputes; never cached by clients.
@router.api_route("/health", methods=["GET", "HEAD"])
def health(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    now = time.monotonic()
    body = _cache["body"]
    if body is None or now - _cache["at"] >= CACHE_SECONDS:
        body = {
            "status": "ok",
            "version": "1.0.0",
            "sources": get_orchestrator(request.app).statuses(),
        }
        _cache["at"], _cache["body"] = now, body
    return body


@router.get("/health/deep")
async def health_deep(request: Request):
    """Admin only: loopback clients (Nginx also allows 127.0.0.1 only). Not in the contract."""
    host = request.client.host if request.client else ""
    if host not in LOOPBACK:
        return Response(status_code=404)
    body = await get_orchestrator(request.app).deep()
    body["checked_at"] = int(time.time())
    return Response(content=json.dumps(body), media_type="application/json",
                    headers={"Cache-Control": "no-store"})

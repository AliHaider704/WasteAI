# File: server/app/routes/health.py
import time

from fastapi import APIRouter, Request, Response

from app.orchestrator import get_orchestrator

router = APIRouter()
LOOPBACK = {"127.0.0.1", "::1"}


@router.get("/health")
def health(request: Request):
    return {
        "status": "ok",
        "version": "1.0.0",
        "sources": get_orchestrator(request.app).statuses(),
    }


@router.get("/health/deep")
async def health_deep(request: Request):
    """Admin only: loopback clients (Nginx also allows 127.0.0.1 only). Not in the contract."""
    host = request.client.host if request.client else ""
    if host not in LOOPBACK:
        return Response(status_code=404)
    body = await get_orchestrator(request.app).deep()
    body["checked_at"] = int(time.time())
    return body

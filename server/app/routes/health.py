# File: server/app/routes/health.py
from fastapi import APIRouter, Request

from app.orchestrator import get_orchestrator

router = APIRouter()


@router.get("/health")
def health(request: Request):
    return {
        "status": "ok",
        "version": "1.0.0",
        "sources": get_orchestrator(request.app).statuses(),
    }

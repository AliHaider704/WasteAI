# File: server/app/main.py
"""FastAPI entry point: uvicorn app.main:app --port 8100"""
import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import cache
from app.config import get_settings
from app.errors import AppError, error_response
from app.logging_setup import setup_logging
from app.orchestrator import get_orchestrator
from app.routes import categories, classify, feedback, health, log

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
        "media-src 'self' blob:; font-src 'self'; connect-src 'self'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(self), microphone=(), geolocation=()",
}

setup_logging(get_settings().log_level)
ACCESS_LOG = logging.getLogger("wasteai.access")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: build the orchestrator (loads the model if active), purge old cache rows."""
    orch = get_orchestrator(app)
    try:  # self-tests must never block startup beyond 10 s
        await asyncio.wait_for(orch.startup_selftests(), 10)
    except Exception as exc:
        ACCESS_LOG.warning("selftest_skipped", extra={"event": "selftest_skipped",
                                                      "source_status": {"error": type(exc).__name__}})
    await cache.purge_expired()
    yield


app = FastAPI(
    title="Waste AI", version=get_settings().app_version,
    docs_url=None, redoc_url=None, lifespan=lifespan,
)

# Same-origin only: no cross-origin origins are allowed.
app.add_middleware(CORSMiddleware, allow_origins=[], allow_methods=["GET", "POST"])


@app.middleware("http")
async def add_request_id_and_headers(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    t0 = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
    finally:
        route = getattr(request.scope.get("route"), "path", "unmatched")
        ACCESS_LOG.log(
            logging.ERROR if status >= 500 else logging.INFO,
            "request",
            extra={
                "event": "request",
                "request_id": request.state.request_id,
                "route": route,
                "status": status,
                "elapsed_ms": int((time.perf_counter() - t0) * 1000),
                "source_status": getattr(request.state, "source_status", None),
            },
        )
    for k, v in SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    return response


@app.exception_handler(AppError)
async def _app_error(request: Request, exc: AppError):
    return error_response(request, exc.code, exc.headers)


@app.exception_handler(RequestValidationError)
async def _validation(request: Request, exc: RequestValidationError):
    return error_response(request, "invalid_request")


@app.exception_handler(StarletteHTTPException)
async def _http(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 413:
        return error_response(request, "image_too_large")
    return error_response(request, "invalid_request" if exc.status_code < 500 else "internal_error")


@app.exception_handler(Exception)
async def _unexpected(request: Request, exc: Exception):
    ACCESS_LOG.error("unhandled", extra={"event": "unhandled", "detail": type(exc).__name__,
                                         "request_id": getattr(request.state, "request_id", None)})
    return error_response(request, "internal_error")


for module in (health, categories, classify, feedback, log):
    app.include_router(module.router, prefix="/api/v1")

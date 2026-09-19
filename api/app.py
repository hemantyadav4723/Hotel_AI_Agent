"""Production-oriented FastAPI application entry point.

The API is intentionally layered on top of the existing hotel business and
SQLite modules. The CLI remains a supported client of the same business layer.
"""

import logging
import time
import uuid
from pathlib import Path
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from api.config import settings
from api.monitoring import record_request
from api.routes import admin, ai, auth, experience, finance, guests, hotel, hr, inventory, operations, reports, system
from database.database import initialize_database
from database.audit_db import set_request_id, reset_request_id
from ai.logging import configure_ai_logging
from utils.production_logging import configure_production_logging

logger = logging.getLogger("yadav_hotel.api")
error_logger = logging.getLogger("yadav_hotel.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_production_logging()
    configure_ai_logging()
    initialize_database()
    if settings.is_production:
        from ai.production import validate_production_configuration
        configuration = validate_production_configuration()
        if not configuration["ready"]:
            raise RuntimeError("Production security/configuration validation failed: " + "; ".join(configuration["issues"]))
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=(
        "Enterprise API layer for YADAV HOTEL AI AGENT PRO. "
        "All business data remains in the existing SQLite/business architecture."
    ),
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
    lifespan=lifespan,
)

allow_all = "*" in settings.cors_origins
app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.trusted_hosts))
if settings.is_production and settings.force_https:
    app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=not allow_all,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

_rate_windows: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def reliability_middleware(request: Request, call_next):
    supplied_request_id = request.headers.get("X-Request-ID", "").strip()
    request_id = supplied_request_id[:128] if supplied_request_id else str(uuid.uuid4())
    if len(request.url.path) > 2048 or len(str(request.url)) > 8192:
        return JSONResponse(status_code=414, content={"detail": "Request URI is too long.", "request_id": request_id}, headers={"X-Request-ID": request_id})
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > 1_048_576:
                return JSONResponse(status_code=413, content={"detail": "Request body is too large.", "request_id": request_id}, headers={"X-Request-ID": request_id})
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length.", "request_id": request_id}, headers={"X-Request-ID": request_id})
    started = time.perf_counter()

    def finalize_response(response, error=False):
        elapsed_ms = (time.perf_counter() - started) * 1000
        record_request(response.status_code, elapsed_ms, error=error or response.status_code >= 500)
        logger.info(
            "api_request request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
            request_id, request.method, request.url.path, response.status_code, elapsed_ms,
        )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-ms"] = f"{elapsed_ms:.2f}"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy-Report-Only"] = "default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.url.path.startswith("/api/v1/auth/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    if len(request.url.path) > 2048 or len(str(request.url)) > 8192:
        return finalize_response(JSONResponse(status_code=414, content={"detail": "Request URI is too long.", "request_id": request_id}))
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > 1_048_576:
                return finalize_response(JSONResponse(status_code=413, content={"detail": "Request body is too large.", "request_id": request_id}))
        except ValueError:
            return finalize_response(JSONResponse(status_code=400, content={"detail": "Invalid Content-Length.", "request_id": request_id}))

    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = _rate_windows[client]
    while window and now - window[0] >= 60:
        window.popleft()
    if len(window) >= settings.rate_limit_per_minute:
        return finalize_response(JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded.", "request_id": request_id},
            headers={"Retry-After": "60", "X-Request-ID": request_id},
        ))
    window.append(now)

    request_token = set_request_id(request_id)
    try:
        response = await call_next(request)
    except Exception as exc:
        error_logger.exception("Unhandled API error request_id=%s method=%s path=%s error=%s", request_id, request.method, request.url.path, type(exc).__name__)
        response = JSONResponse(status_code=500, content={"detail": "Internal server error.", "request_id": request_id})
    finally:
        reset_request_id(request_token)
    return finalize_response(response)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc) or "Invalid request."})


@app.exception_handler(PermissionError)
async def permission_error_handler(request: Request, exc: PermissionError):
    return JSONResponse(status_code=403, content={"detail": str(exc) or "Permission denied."})


for router in (
    system.router,
    auth.router,
    hotel.router,
    guests.router,
    operations.router,
    finance.router,
    inventory.router,
    hr.router,
    experience.router,
    reports.router,
    admin.router,
    ai.router,
):
    app.include_router(router, prefix=settings.prefix)



# Serve the admin dashboard from the same origin as the API.
# Production deployments serve the deterministic build artifact when present;
# development/test environments continue to serve the source dashboard.
DASHBOARD_SOURCE_DIR = Path(__file__).resolve().parent.parent / "dashboard"
DASHBOARD_DIST_DIR = DASHBOARD_SOURCE_DIR / "dist"
if settings.is_production:
    if not DASHBOARD_DIST_DIR.is_dir():
        raise RuntimeError("Production dashboard build is missing. Run: python dashboard/build.py")
    DASHBOARD_DIR = DASHBOARD_DIST_DIR
else:
    DASHBOARD_DIR = DASHBOARD_SOURCE_DIR
if DASHBOARD_DIR.is_dir():
    app.mount("/dashboard", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard")


@app.get("/dashboard", include_in_schema=False)
def dashboard_redirect():
    return RedirectResponse(url="/dashboard/")

@app.get("/", tags=["System"])
def root():
    return {"service": settings.app_name, "version": settings.version, "api": settings.prefix, "docs": "/docs", "status": "ok"}

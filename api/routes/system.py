from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api.config import settings
from api.monitoring import snapshot
from database.database import get_connection
from ai.production import ai_health, database_health, validate_production_configuration

router = APIRouter(tags=["System"])


@router.get("/health")
def health():
    connection = get_connection()
    try:
        connection.execute("SELECT 1").fetchone()
    finally:
        connection.close()
    return {"status": "ok", "service": settings.app_name, "version": settings.version, "database": "ok"}


@router.get("/health/live")
def liveness():
    return {"status": "alive", "service": settings.app_name, "version": settings.version}


@router.get("/health/ready")
def readiness():
    db = database_health()
    config = validate_production_configuration()
    ready = db["status"] == "ok" and config["ready"]
    payload = {"status": "ready" if ready else "degraded", "database": db, "configuration": config}
    if not ready:
        return JSONResponse(status_code=503, content=payload)
    return payload


@router.get("/health/ai")
def ai_readiness():
    return ai_health()


@router.get("/monitoring")
def monitoring():
    """Operational metrics without request payloads or secrets."""
    return {"status": "ok", "metrics": snapshot()}


@router.get("/version")
def version():
    return {"service": settings.app_name, "version": settings.version, "api_version": "v1", "phase": "6 - FastAPI Backend"}

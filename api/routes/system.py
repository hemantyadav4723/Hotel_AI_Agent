from fastapi import APIRouter

from api.config import settings
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


@router.get("/health/ready")
def readiness():
    db = database_health()
    config = validate_production_configuration()
    ready = db["status"] == "ok" and config["ready"]
    return {"status": "ready" if ready else "degraded", "database": db, "configuration": config}


@router.get("/health/ai")
def ai_readiness():
    return ai_health()


@router.get("/version")
def version():
    return {"service": settings.app_name, "version": settings.version, "api_version": "v1", "phase": "6 - FastAPI Backend"}

"""Start the YADAV HOTEL FastAPI backend.

Runtime values are environment-driven. For production, inject secrets and
configuration through the deployment environment/secret manager.

Usage from the Hotel_AI_Agent directory:
    python run_api.py
"""

import uvicorn

from api.config import settings


if __name__ == "__main__":
    uvicorn.run(
        "api.app:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        reload=False,
        proxy_headers=settings.proxy_headers,
        forwarded_allow_ips=settings.forwarded_allow_ips,
        access_log=settings.access_log,
        log_level=settings.log_level.lower(),
    )

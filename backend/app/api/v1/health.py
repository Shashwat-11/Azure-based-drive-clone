from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.dependencies.database import get_db
from app.dependencies.redis import get_redis
from app.storage.azure_blob import AzureBlobStorageBackend

logger = get_logger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "checks": {},
    }


@router.get("/live")
async def liveness_check():
    return {"status": "alive"}


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):  # noqa: B008
    checks: dict[str, dict] = {}

    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = {"status": "healthy"}
    except Exception as exc:
        checks["database"] = {"status": "unhealthy", "error": str(exc)}

    try:
        redis_client = await get_redis()
        await redis_client.ping()
        checks["redis"] = {"status": "healthy"}
    except Exception as exc:
        checks["redis"] = {"status": "unhealthy", "error": str(exc)}

    try:
        storage = AzureBlobStorageBackend()
        if await storage.health_check():
            checks["storage"] = {"status": "healthy"}
        else:
            checks["storage"] = {"status": "unhealthy"}
    except Exception as exc:
        checks["storage"] = {"status": "unhealthy", "error": str(exc)}

    all_healthy = all(c.get("status") == "healthy" for c in checks.values())

    return {
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks,
    }


@router.get("/startup")
async def startup_check():
    return {"status": "started"}

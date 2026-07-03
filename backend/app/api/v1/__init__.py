from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.collaboration import router as collaboration_router
from app.api.v1.discovery import router as discovery_router
from app.api.v1.files import router as files_router
from app.api.v1.folders import router as folders_router
from app.api.v1.health import router as health_router
from app.api.v1.versions import router as versions_router

router = APIRouter(prefix="/api/v1")
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(folders_router)
router.include_router(files_router)
router.include_router(collaboration_router)
router.include_router(versions_router)
router.include_router(discovery_router)

from __future__ import annotations

from app.services.storage import StorageService

_storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service


def set_storage_service(service: StorageService) -> None:
    global _storage_service
    _storage_service = service


def reset_storage_service() -> None:
    global _storage_service
    _storage_service = None

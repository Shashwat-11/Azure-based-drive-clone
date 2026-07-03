from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator

from app.core.logging_config import get_logger
from app.core.retry import with_retry
from app.storage.azure_blob import AzureBlobStorageBackend
from app.storage.base import StorageBackend

logger = get_logger(__name__)


class StorageService:
    def __init__(self, backend: StorageBackend | None = None) -> None:
        self._backend = backend

    async def _get_backend(self) -> StorageBackend:
        if self._backend is None:
            self._backend = AzureBlobStorageBackend()
        return self._backend

    def generate_blob_name(self, user_id: uuid.UUID) -> str:
        return f"{user_id}/{uuid.uuid4()}"

    async def upload_and_hash(
        self,
        blob_name: str,
        stream: AsyncIterator[bytes],
        *,
        content_type: str | None = None,
    ) -> tuple[int, str]:
        backend = await self._get_backend()
        hasher = hashlib.sha256()
        total_size = 0

        async def hashing_stream() -> AsyncIterator[bytes]:
            nonlocal total_size
            async for chunk in stream:
                hasher.update(chunk)
                total_size += len(chunk)
                yield chunk

        await with_retry(
            lambda: backend.upload_stream(
                blob_name=blob_name, stream=hashing_stream(), content_type=content_type),
            max_retries=3, base_delay=1.0,
        )

        checksum = hasher.hexdigest()
        logger.info("blob_uploaded_with_hash", blob_name=blob_name, size=total_size, checksum=checksum)
        return total_size, checksum

    async def download_stream(self, blob_name: str) -> AsyncIterator[bytes]:
        backend = await self._get_backend()
        async for chunk in backend.download_stream(blob_name):
            yield chunk

    async def delete_blob(self, blob_name: str) -> None:
        backend = await self._get_backend()
        await backend.delete(blob_name)
        logger.info("blob_deleted_via_service", blob_name=blob_name)

    async def delete_blobs(self, blob_names: list[str]) -> None:
        backend = await self._get_backend()
        await backend.delete_batch(blob_names)
        logger.info("blobs_deleted_batch", count=len(blob_names))

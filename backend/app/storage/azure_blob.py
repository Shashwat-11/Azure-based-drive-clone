from __future__ import annotations

from collections.abc import AsyncIterator

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import BlobServiceClient, ContainerClient

from app.config.settings import settings
from app.core.exceptions import ServiceUnavailableError, StorageError
from app.core.logging_config import get_logger
from app.storage.base import StorageBackend

logger = get_logger(__name__)


class AzureBlobStorageBackend(StorageBackend):
    def __init__(self) -> None:
        self._service_client: BlobServiceClient | None = None
        self._container_client: ContainerClient | None = None
        self._container_name = settings.AZURE_STORAGE_CONTAINER_NAME

    async def _get_service_client(self) -> BlobServiceClient:
        if self._service_client is None:
            if not settings.AZURE_STORAGE_ENABLED:
                raise ServiceUnavailableError("Azure Blob Storage is not configured")
            if settings.AZURE_STORAGE_CONNECTION_STRING:
                conn_str = settings.AZURE_STORAGE_CONNECTION_STRING.get_secret_value()
                self._service_client = BlobServiceClient.from_connection_string(conn_str)
            elif settings.AZURE_STORAGE_ACCOUNT_NAME and settings.AZURE_STORAGE_ACCOUNT_KEY:
                account_url = (
                    f"https://{settings.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
                )
                if settings.AZURE_STORAGE_USE_AZURITE:
                    account_url = settings.AZURE_STORAGE_AZURITE_URL
                account_key = settings.AZURE_STORAGE_ACCOUNT_KEY.get_secret_value()
                self._service_client = BlobServiceClient(
                    account_url=account_url,
                    credential=account_key,
                )
            else:
                raise ServiceUnavailableError("Azure Blob Storage credentials missing")
            logger.info(
                "azure_blob_service_client_created",
                container=self._container_name,
                account=settings.AZURE_STORAGE_ACCOUNT_NAME,
            )
        return self._service_client

    async def _get_container_client(self) -> ContainerClient:
        if self._container_client is None:
            service = await self._get_service_client()
            self._container_client = service.get_container_client(self._container_name)
        return self._container_client

    async def upload(
        self,
        blob_name: str,
        data: bytes,
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        try:
            container = await self._get_container_client()
            blob_client = container.get_blob_client(blob_name)
            content_settings = ContentSettings(content_type=content_type) if content_type else None
            await blob_client.upload_blob(
                data,
                metadata=metadata,
                content_settings=content_settings,
                overwrite=True,
            )
            logger.info("blob_uploaded", blob_name=blob_name, size=len(data))
            return blob_name
        except AzureError as exc:
            logger.error(
                "blob_upload_failed",
                blob_name=blob_name,
                error=str(exc),
            )
            raise StorageError(f"Failed to upload blob: {blob_name}") from exc

    async def upload_stream(
        self,
        blob_name: str,
        stream: AsyncIterator[bytes],
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        try:
            container = await self._get_container_client()
            blob_client = container.get_blob_client(blob_name)
            content_settings = ContentSettings(content_type=content_type) if content_type else None

            total_size = 0
            chunks: list[bytes] = []
            async for chunk in stream:
                chunks.append(chunk)
                total_size += len(chunk)

            data = b"".join(chunks)
            await blob_client.upload_blob(
                data,
                overwrite=True,
                content_settings=content_settings,
                metadata=metadata,
            )
            logger.info("blob_stream_uploaded", blob_name=blob_name, size=total_size)
            return blob_name
        except AzureError as exc:
            logger.error(
                "blob_stream_upload_failed",
                blob_name=blob_name,
                error=str(exc),
            )
            raise StorageError(f"Failed to upload blob stream: {blob_name}") from exc

    async def download(self, blob_name: str) -> bytes:
        try:
            container = await self._get_container_client()
            blob_client = container.get_blob_client(blob_name)
            stream = await blob_client.download_blob()
            data = await stream.readall()
            logger.info("blob_downloaded", blob_name=blob_name, size=len(data))
            return data
        except ResourceNotFoundError:
            raise StorageError(f"Blob not found: {blob_name}", code="BLOB_NOT_FOUND") from None
        except AzureError as exc:
            logger.error(
                "blob_download_failed",
                blob_name=blob_name,
                error=str(exc),
            )
            raise StorageError(f"Failed to download blob: {blob_name}") from exc

    async def download_stream(self, blob_name: str) -> AsyncIterator[bytes]:
        try:
            container = await self._get_container_client()
            blob_client = container.get_blob_client(blob_name)
            downloader = await blob_client.download_blob()

            async for chunk in downloader.chunks():
                if chunk:
                    yield chunk

            logger.info("blob_download_stream_complete", blob_name=blob_name)
        except ResourceNotFoundError:
            raise StorageError(f"Blob not found: {blob_name}", code="BLOB_NOT_FOUND") from None
        except AzureError as exc:
            logger.error(
                "blob_stream_download_failed",
                blob_name=blob_name,
                error=str(exc),
            )
            raise StorageError(f"Failed to download blob stream: {blob_name}") from exc

    async def delete(self, blob_name: str) -> None:
        try:
            container = await self._get_container_client()
            await container.delete_blob(blob_name)
            logger.info("blob_deleted", blob_name=blob_name)
        except ResourceNotFoundError:
            logger.warning("blob_delete_not_found", blob_name=blob_name)
        except AzureError as exc:
            logger.error(
                "blob_delete_failed",
                blob_name=blob_name,
                error=str(exc),
            )
            raise StorageError(f"Failed to delete blob: {blob_name}") from exc

    async def delete_batch(self, blob_names: list[str]) -> None:
        try:
            container = await self._get_container_client()
            for blob_name in blob_names:
                try:
                    await container.delete_blob(blob_name)
                except ResourceNotFoundError:
                    logger.warning("blob_delete_batch_not_found", blob_name=blob_name)
            logger.info("blob_delete_batch_complete", count=len(blob_names))
        except AzureError as exc:
            logger.error(
                "blob_delete_batch_failed",
                count=len(blob_names),
                error=str(exc),
            )
            raise StorageError("Failed to delete blob batch") from exc

    async def exists(self, blob_name: str) -> bool:
        try:
            container = await self._get_container_client()
            blob_client = container.get_blob_client(blob_name)
            return await blob_client.exists()
        except AzureError as exc:
            logger.error(
                "blob_exists_check_failed",
                blob_name=blob_name,
                error=str(exc),
            )
            return False

    async def copy(self, source_blob: str, destination_blob: str) -> str:
        try:
            container = await self._get_container_client()
            source_client = container.get_blob_client(source_blob)
            destination_client = container.get_blob_client(destination_blob)

            source_url = source_client.url
            await destination_client.start_copy_from_url(source_url)
            logger.info(
                "blob_copy_started",
                source=source_blob,
                destination=destination_blob,
            )
            return destination_blob
        except ResourceNotFoundError:
            raise StorageError(
                f"Source blob not found: {source_blob}", code="BLOB_NOT_FOUND"
            ) from None
        except AzureError as exc:
            logger.error(
                "blob_copy_failed",
                source=source_blob,
                destination=destination_blob,
                error=str(exc),
            )
            raise StorageError(f"Failed to copy blob: {source_blob}") from exc

    async def move(self, source_blob: str, destination_blob: str) -> str:
        await self.copy(source_blob, destination_blob)
        await self.delete(source_blob)
        logger.info(
            "blob_moved",
            source=source_blob,
            destination=destination_blob,
        )
        return destination_blob

    async def health_check(self) -> bool:
        if not settings.AZURE_STORAGE_ENABLED:
            logger.warning("azure_blob_health_check_skipped_not_configured")
            return True
        try:
            container = await self._get_container_client()
            await container.get_container_properties()
            logger.info("azure_blob_health_check_succeeded")
            return True
        except AzureError as exc:
            logger.error(
                "azure_blob_health_check_failed",
                error=str(exc),
            )
            return False

    async def close(self) -> None:
        if self._service_client is not None:
            await self._service_client.close()
            self._service_client = None
            self._container_client = None
            logger.info("azure_blob_service_client_closed")

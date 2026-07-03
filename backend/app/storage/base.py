from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class StorageBackend(ABC):
    @abstractmethod
    async def upload(
        self,
        blob_name: str,
        data: bytes,
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        ...

    @abstractmethod
    async def upload_stream(
        self,
        blob_name: str,
        stream: AsyncIterator[bytes],
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        ...

    @abstractmethod
    async def download(self, blob_name: str) -> bytes:
        ...

    @abstractmethod
    async def download_stream(self, blob_name: str) -> AsyncIterator[bytes]:
        ...

    @abstractmethod
    async def delete(self, blob_name: str) -> None:
        ...

    @abstractmethod
    async def delete_batch(self, blob_names: list[str]) -> None:
        ...

    @abstractmethod
    async def exists(self, blob_name: str) -> bool:
        ...

    @abstractmethod
    async def copy(self, source_blob: str, destination_blob: str) -> str:
        ...

    @abstractmethod
    async def move(self, source_blob: str, destination_blob: str) -> str:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...

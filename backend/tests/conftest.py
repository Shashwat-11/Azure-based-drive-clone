from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config.settings import Settings, get_settings

TEST_SETTINGS = Settings(
    ENVIRONMENT="development",
    DB_NAME=f"test_drive_{uuid.uuid4().hex[:8]}",
    DB_POOL_SIZE=5,
    DB_POOL_OVERFLOW=2,
    DB_ECHO=False,
    REDIS_DB=1,
    REDIS_PASSWORD=None,
    AZURE_STORAGE_ACCOUNT_NAME=None,
    AZURE_STORAGE_ACCOUNT_KEY=None,
    AZURE_STORAGE_CONNECTION_STRING=None,
    JWT_SECRET_KEY="test-secret-key-for-testing-only",
    RATE_LIMIT_ENABLED=False,
    SECURE_HEADERS_ENABLED=False,
)


class MockStorageBackend:
    def __init__(self):
        self.blobs: dict[str, bytes] = {}
        self.deleted: list[str] = []

    async def upload(self, blob_name, data, *, content_type=None, metadata=None):
        self.blobs[blob_name] = data
        return blob_name

    async def upload_stream(self, blob_name, stream, *, content_type=None, metadata=None):
        chunks = []
        async for chunk in stream:
            chunks.append(chunk)
        self.blobs[blob_name] = b"".join(chunks)
        return blob_name

    async def download(self, blob_name):
        return self.blobs.get(blob_name, b"")

    async def download_stream(self, blob_name):
        data = self.blobs.get(blob_name, b"")
        chunk_size = 64 * 1024
        for i in range(0, len(data), chunk_size):
            yield data[i : i + chunk_size]

    async def delete(self, blob_name):
        self.deleted.append(blob_name)
        self.blobs.pop(blob_name, None)

    async def delete_batch(self, blob_names):
        for name in blob_names:
            await self.delete(name)

    async def exists(self, blob_name):
        return blob_name in self.blobs

    async def copy(self, source_blob, destination_blob):
        if source_blob in self.blobs:
            self.blobs[destination_blob] = self.blobs[source_blob]
        return destination_blob

    async def move(self, source_blob, destination_blob):
        await self.copy(source_blob, destination_blob)
        await self.delete(source_blob)
        return destination_blob

    async def health_check(self):
        return True

    async def close(self):
        pass


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    try:
        from app.models import Base  # noqa: F811

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def app(db_session: AsyncSession) -> AsyncIterator[FastAPI]:
    from app.dependencies.database import get_db
    from app.dependencies.storage import get_storage_service, reset_storage_service
    from app.main import create_app
    from app.services.storage import StorageService

    get_settings()

    app_instance = create_app()

    async def override_get_db():
        yield db_session

    mock_backend = MockStorageBackend()
    mock_storage = StorageService(backend=mock_backend)

    def override_get_storage():
        return mock_storage

    app_instance.dependency_overrides[get_db] = override_get_db
    app_instance.dependency_overrides[get_storage_service] = override_get_storage

    yield app_instance

    app_instance.dependency_overrides.clear()
    reset_storage_service()


@pytest_asyncio.fixture(scope="function")
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

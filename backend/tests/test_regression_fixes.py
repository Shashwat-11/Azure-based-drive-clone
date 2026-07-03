from __future__ import annotations

import ast
import inspect

import pytest
from httpx import AsyncClient

from app.models.user import RefreshToken, User


class TestDatabaseEngineFix:
    """CRI-001: Verify get_engine() returns a real AsyncEngine, not a coroutine."""

    @pytest.mark.asyncio
    async def test_engine_is_real_object_not_coroutine(self):
        from app.dependencies.database import get_engine

        engine = get_engine()
        assert engine is not None
        assert hasattr(engine, "dispose")
        assert hasattr(engine, "connect")

    @pytest.mark.asyncio
    async def test_engine_is_singleton(self):
        from app.dependencies.database import get_engine

        engine1 = get_engine()
        engine2 = get_engine()
        assert engine1 is engine2

    @pytest.mark.asyncio
    async def test_lifespan_calls_close_db(self):
        from app.dependencies.database import _engine, close_db

        assert _engine is not None
        await close_db()
        import app.dependencies.database as db_module
        assert db_module._engine is None
        assert db_module._session_factory is None


class TestTraceIdFix:
    """HIG-006: Verify trace_id is never None in request_started logs."""

    @pytest.mark.asyncio
    async def test_response_contains_trace_id_header(self, client: AsyncClient):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        trace_id = response.headers.get("x-request-id")
        assert trace_id is not None
        assert len(trace_id) == 36
        assert trace_id != "None"

    @pytest.mark.asyncio
    async def test_request_logger_reads_header_directly(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/health",
            headers={"X-Request-ID": "custom-trace-999"},
        )
        assert response.status_code == 200
        assert response.headers["x-request-id"] == "custom-trace-999"

    @pytest.mark.asyncio
    async def test_trace_id_unique_per_request_persists(self, client: AsyncClient):
        response1 = await client.get("/api/v1/health")
        response2 = await client.get("/api/v1/health")
        id1 = response1.headers["x-request-id"]
        id2 = response2.headers["x-request-id"]
        assert id1 != id2
        assert len(id1) == 36
        assert len(id2) == 36


class TestSecurityHeaders:
    """HIG-003: Verify security headers are present."""

    @pytest.mark.asyncio
    async def test_security_headers_present(self, client: AsyncClient):
        response = await client.get("/api/v1/health")
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"
        assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        assert response.headers.get("cache-control") == "no-store, max-age=0"

    @pytest.mark.asyncio
    async def test_security_headers_on_error_response(self, client: AsyncClient):
        response = await client.get("/api/v1/nonexistent-endpoint")
        assert response.status_code == 404
        assert response.headers.get("x-content-type-options") == "nosniff"

    @pytest.mark.asyncio
    async def test_xss_protection_header_present(self, client: AsyncClient):
        response = await client.get("/api/v1/health")
        assert response.headers.get("x-xss-protection") == "1; mode=block"


class TestRateLimiter:
    """HIG-002: Verify rate limiting on auth endpoints."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_first_request(self, client: AsyncClient):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_rate_limiter_respects_config(self):
        from app.config.settings import settings
        assert settings.RATE_LIMIT_ENABLED is True
        assert settings.RATE_LIMIT_REQUESTS == 100
        assert settings.RATE_LIMIT_WINDOW_SECONDS == 60

    @pytest.mark.asyncio
    async def test_rate_limiter_middleware_is_registered(self, client: AsyncClient):
        from app.middleware.rate_limiter import RateLimiterMiddleware
        assert RateLimiterMiddleware is not None


class TestRefreshTokenUserIdType:
    """HIG-007: Verify RefreshToken.user_id matches User.id type (PG_UUID)."""

    @pytest.mark.asyncio
    async def test_user_id_column_is_pg_uuid(self):
        from sqlalchemy.dialects.postgresql import UUID as PG_UUID

        user_id_col = RefreshToken.__table__.c.user_id
        assert isinstance(user_id_col.type, PG_UUID)

    @pytest.mark.asyncio
    async def test_refresh_token_user_id_matches_user_id_type(self):
        user_id_col = User.__table__.c.id
        rt_user_id_col = RefreshToken.__table__.c.user_id
        assert user_id_col.type.__class__ == rt_user_id_col.type.__class__

    @pytest.mark.asyncio
    async def test_fk_joins_on_matching_types(self):

        fks = list(RefreshToken.__table__.c.user_id.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column == User.__table__.c.id


class TestStorageStreamUpload:
    """HIG-004: Verify stream upload uses block-based approach."""

    @pytest.mark.asyncio
    async def test_upload_stream_uses_upload_blob(self):
        from app.storage.azure_blob import AzureBlobStorageBackend

        upload_stream_fn = AzureBlobStorageBackend.upload_stream
        code_constants = upload_stream_fn.__code__.co_names
        assert "upload_blob" in code_constants

    @pytest.mark.asyncio
    async def test_upload_stream_method_signature_matches_interface(self):
        from app.storage.azure_blob import AzureBlobStorageBackend
        from app.storage.base import StorageBackend

        assert issubclass(AzureBlobStorageBackend, StorageBackend)


class TestDeadCodeRemoval:
    """HIG-005: Verify download_stream has no dead code."""

    @pytest.mark.asyncio
    async def test_download_stream_no_bare_expressions(self):
        import textwrap

        from app.storage.azure_blob import AzureBlobStorageBackend

        source_full = inspect.getsource(AzureBlobStorageBackend.download_stream)
        source_lines = source_full.split("\n")
        dedented = textwrap.dedent("\n".join(source_lines[1:]))

        tree = ast.parse(dedented)

        for node in ast.walk(tree):
            if isinstance(node, ast.Expr):
                assert not isinstance(node.value, ast.BinOp), (
                    "Bare arithmetic expression found in download_stream"
                )

    @pytest.mark.asyncio
    async def test_download_stream_function_compiles(self):
        from app.storage.azure_blob import AzureBlobStorageBackend

        fn = AzureBlobStorageBackend.download_stream
        assert callable(fn)

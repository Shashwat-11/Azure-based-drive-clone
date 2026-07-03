from __future__ import annotations

import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.models.user import UserRole
from app.repositories.user import UserRepository


async def _create_user(db: AsyncSession, email: str = "test@example.com") -> tuple[uuid.UUID, str]:
    repo = UserRepository(db)
    user = await repo.create(email=email, password_hash=hash_password("securePassword123"), full_name="Test User")
    token = create_access_token(user.id, UserRole.USER.value)
    return user.id, token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _upload(client: AsyncClient, token: str, name: str = "test.txt", content: bytes = b"hello") -> str:
    resp = await client.post("/api/v1/files/upload",
        files={"file": (name, io.BytesIO(content), "text/plain")}, headers=_auth_headers(token))
    assert resp.status_code == 201
    return resp.json()["id"]


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_by_filename(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        await _upload(client, token, name="report.pdf")
        await _upload(client, token, name="notes.txt")

        resp = await client.get("/api/v1/search?query=report", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_search_empty_query_returns_all(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        await _upload(client, token, name="a.txt")
        await _upload(client, token, name="b.txt")

        resp = await client.get("/api/v1/search", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2

    @pytest.mark.asyncio
    async def test_search_by_extension(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        await _upload(client, token, name="doc.pdf")
        await _upload(client, token, name="notes.txt")

        resp = await client.get("/api/v1/search?extension=txt", headers=_auth_headers(token))
        assert resp.status_code == 200
        results = resp.json()["files"]
        assert all("txt" in f.get("extension", "") for f in results)

    @pytest.mark.asyncio
    async def test_search_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/search?query=test")
        assert resp.status_code == 401


class TestTags:
    @pytest.mark.asyncio
    async def test_create_tag(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        resp = await client.post("/api/v1/tags", json={"name": "important"},
                                 headers=_auth_headers(token))
        assert resp.status_code == 201
        assert resp.json()["name"] == "important"

    @pytest.mark.asyncio
    async def test_list_tags(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        await client.post("/api/v1/tags", json={"name": "work"}, headers=_auth_headers(token))
        await client.post("/api/v1/tags", json={"name": "personal"}, headers=_auth_headers(token))

        resp = await client.get("/api/v1/tags", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    @pytest.mark.asyncio
    async def test_delete_tag(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        create_resp = await client.post("/api/v1/tags", json={"name": "todelete"},
                                        headers=_auth_headers(token))
        tag_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/tags/{tag_id}", headers=_auth_headers(token))
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_assign_tag_to_file(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token)
        tag_resp = await client.post("/api/v1/tags", json={"name": "labeled"},
                                     headers=_auth_headers(token))
        tag_id = tag_resp.json()["id"]

        resp = await client.post(
            f"/api/v1/files/{fid}/tags", json={"tag_id": tag_id}, headers=_auth_headers(token))
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_search_by_tag(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token)
        tag_resp = await client.post("/api/v1/tags", json={"name": "findme"},
                                     headers=_auth_headers(token))
        tag_id = tag_resp.json()["id"]
        await client.post(f"/api/v1/files/{fid}/tags", json={"tag_id": tag_id},
                          headers=_auth_headers(token))

        resp = await client.get(f"/api/v1/search?tag_id={tag_id}", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1


class TestFavorites:
    @pytest.mark.asyncio
    async def test_add_favorite(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token)

        resp = await client.post(f"/api/v1/favorites/{fid}", headers=_auth_headers(token))
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_list_favorites(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token)
        await client.post(f"/api/v1/favorites/{fid}", headers=_auth_headers(token))

        resp = await client.get("/api/v1/favorites", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_remove_favorite(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token)
        await client.post(f"/api/v1/favorites/{fid}", headers=_auth_headers(token))

        resp = await client.delete(f"/api/v1/favorites/{fid}", headers=_auth_headers(token))
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_search_favorite_only(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid1 = await _upload(client, token, name="fav.txt")
        await _upload(client, token, name="notfav.txt")
        await client.post(f"/api/v1/favorites/{fid1}", headers=_auth_headers(token))

        resp = await client.get("/api/v1/search?favorite_only=true", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1


class TestRecentFiles:
    @pytest.mark.asyncio
    async def test_list_recent(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        await _upload(client, token)

        resp = await client.get("/api/v1/recent", headers=_auth_headers(token))
        assert resp.status_code == 200


class TestMetadata:
    @pytest.mark.asyncio
    async def test_update_file_metadata(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token)

        resp = await client.patch(
            f"/api/v1/files/{fid}/metadata",
            json={"description": "My document", "color_label": "blue"},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "My document"

    @pytest.mark.asyncio
    async def test_update_custom_properties(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload(client, token)

        resp = await client.patch(
            f"/api/v1/files/{fid}/metadata",
            json={"custom_properties": {"category": "reports", "priority": 1}},
            headers=_auth_headers(token),
        )
        assert resp.status_code == 200

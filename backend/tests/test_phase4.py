from __future__ import annotations

import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.models.user import UserRole
from app.repositories.file import FolderRepository
from app.repositories.user import UserRepository


async def _create_user(db: AsyncSession, email: str = "test@example.com") -> tuple[uuid.UUID, str]:
    repo = UserRepository(db)
    user = await repo.create(email=email, password_hash=hash_password("securePassword123"), full_name="Test User")
    token = create_access_token(user.id, UserRole.USER.value)
    return user.id, token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _upload_file(client: AsyncClient, token: str, name: str = "test.txt", content: bytes = b"hello",
                        folder_id: str | None = None) -> str:
    qs = f"?folder_id={folder_id}" if folder_id else ""
    resp = await client.post(f"/api/v1/files/upload{qs}", files={"file": (name, io.BytesIO(content), "text/plain")},
                             headers=_auth_headers(token))
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_folder(client: AsyncClient, token: str, name: str, parent_id: str | None = None) -> str:
    body = {"name": name}
    if parent_id:
        body["parent_id"] = parent_id
    resp = await client.post("/api/v1/folders", json=body, headers=_auth_headers(token))
    assert resp.status_code == 201
    return resp.json()["id"]


class TestFolderMove:
    @pytest.mark.asyncio
    async def test_move_folder_to_root(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        parent_id = await _create_folder(client, token, "Parent")
        child_id = await _create_folder(client, token, "Child", parent_id=parent_id)
        resp = await client.post(f"/api/v1/folders/{child_id}/move", json={"target_parent_id": None},
                                 headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["parent_id"] is None

    @pytest.mark.asyncio
    async def test_cannot_move_into_self(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _create_folder(client, token, "Self")
        resp = await client.post(f"/api/v1/folders/{fid}/move", json={"target_parent_id": fid},
                                 headers=_auth_headers(token))
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_cannot_move_into_descendant(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        a = await _create_folder(client, token, "A")
        b = await _create_folder(client, token, "B", parent_id=a)
        resp = await client.post(f"/api/v1/folders/{a}/move", json={"target_parent_id": b},
                                 headers=_auth_headers(token))
        assert resp.status_code == 422


class TestFileMove:
    @pytest.mark.asyncio
    async def test_move_file_between_folders(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        src = await _create_folder(client, token, "Src")
        dst = await _create_folder(client, token, "Dst")
        fid = await _upload_file(client, token, folder_id=src)
        resp = await client.post(f"/api/v1/files/{fid}/move", json={"target_parent_id": dst},
                                 headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["folder_id"] == dst


class TestFolderCopy:
    @pytest.mark.asyncio
    async def test_copy_folder_in_same_parent(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _create_folder(client, token, "Original")
        await _upload_file(client, token, folder_id=fid)
        resp = await client.post(f"/api/v1/folders/{fid}/copy", json={"target_parent_id": None},
                                 headers=_auth_headers(token))
        assert resp.status_code == 201
        assert resp.json()["name"] == "Original (Copy 1)"
        children = await client.get(f"/api/v1/folders/{resp.json()['id']}/children", headers=_auth_headers(token))
        assert children.status_code == 200


class TestFileCopy:
    @pytest.mark.asyncio
    async def test_copy_file(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload_file(client, token, name="copy-me.txt")
        resp = await client.post(f"/api/v1/files/{fid}/copy", json={"target_parent_id": None},
                                 headers=_auth_headers(token))
        assert resp.status_code == 201
        assert resp.json()["original_filename"] == "copy-me.txt"
        assert resp.json()["id"] != fid


class TestRecursiveDelete:
    @pytest.mark.asyncio
    async def test_delete_folder_recurively_soft_deletes_children(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        parent = await _create_folder(client, token, "Parent")
        child = await _create_folder(client, token, "Child", parent_id=parent)
        fid = await _upload_file(client, token, folder_id=child)
        resp = await client.delete(f"/api/v1/folders/{parent}", headers=_auth_headers(token))
        assert resp.status_code == 200
        get_child = await client.get(f"/api/v1/folders/{child}", headers=_auth_headers(token))
        assert get_child.status_code == 404
        get_file = await client.get(f"/api/v1/files/{fid}", headers=_auth_headers(token))
        assert get_file.status_code == 404


class TestRestore:
    @pytest.mark.asyncio
    async def test_restore_file_from_trash(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload_file(client, token)
        await client.delete(f"/api/v1/files/{fid}", headers=_auth_headers(token))
        resp = await client.post(f"/api/v1/files/{fid}/restore", headers=_auth_headers(token))
        assert resp.status_code == 200
        get_resp = await client.get(f"/api/v1/files/{fid}", headers=_auth_headers(token))
        assert get_resp.status_code == 200

    @pytest.mark.asyncio
    async def test_restore_folder_restores_children(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        parent = await _create_folder(client, token, "P")
        child = await _create_folder(client, token, "C", parent_id=parent)
        fid = await _upload_file(client, token, folder_id=child)
        await client.delete(f"/api/v1/folders/{parent}", headers=_auth_headers(token))
        resp = await client.post(f"/api/v1/folders/{parent}/restore", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert (await client.get(f"/api/v1/folders/{child}", headers=_auth_headers(token))).status_code == 200
        assert (await client.get(f"/api/v1/files/{fid}", headers=_auth_headers(token))).status_code == 200

    @pytest.mark.asyncio
    async def test_cannot_restore_nondeleted(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload_file(client, token)
        resp = await client.post(f"/api/v1/files/{fid}/restore", headers=_auth_headers(token))
        assert resp.status_code == 422


class TestPermanentDelete:
    @pytest.mark.asyncio
    async def test_permanent_delete_removes_record(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload_file(client, token)
        await client.delete(f"/api/v1/files/{fid}", headers=_auth_headers(token))
        resp = await client.delete(f"/api/v1/files/{fid}/permanent", headers=_auth_headers(token))
        assert resp.status_code == 200
        restore = await client.post(f"/api/v1/files/{fid}/restore", headers=_auth_headers(token))
        assert restore.status_code == 404


class TestTrash:
    @pytest.mark.asyncio
    async def test_list_trash(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload_file(client, token)
        await client.delete(f"/api/v1/files/{fid}", headers=_auth_headers(token))
        resp = await client.get("/api/v1/folders/trash/all", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_empty_trash(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload_file(client, token)
        await client.delete(f"/api/v1/files/{fid}", headers=_auth_headers(token))
        resp = await client.post("/api/v1/folders/trash/empty", headers=_auth_headers(token))
        assert resp.status_code == 200
        assert (await client.get("/api/v1/folders/trash/all", headers=_auth_headers(token))).json()["total"] == 0


class TestBreadcrumbs:
    @pytest.mark.asyncio
    async def test_breadcrumbs_shows_path(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        root = await _create_folder(client, token, "Home")
        child = await _create_folder(client, token, "Docs", parent_id=root)
        resp = await client.get(f"/api/v1/folders/{child}/breadcrumbs", headers=_auth_headers(token))
        assert resp.status_code == 200
        crumbs = resp.json()["breadcrumbs"]
        names = [c["name"] for c in crumbs]
        assert "Home" in names
        assert "Docs" in names


class TestFolderSize:
    @pytest.mark.asyncio
    async def test_folder_size_calculates_recursively(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        parent = await _create_folder(client, token, "Data")
        child = await _create_folder(client, token, "Sub", parent_id=parent)
        await _upload_file(client, token, content=b"1234567890", folder_id=parent)
        await _upload_file(client, token, content=b"hello", folder_id=child)
        resp = await client.get(f"/api/v1/folders/{parent}/size", headers=_auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["file_count"] == 2
        assert data["folder_count"] == 1
        assert data["total_size_bytes"] == 15


class TestRename:
    @pytest.mark.asyncio
    async def test_rename_file(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _upload_file(client, token, name="old.txt")
        resp = await client.post(f"/api/v1/files/{fid}/rename", json={"name": "new.txt"},
                                 headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["original_filename"] == "new.txt"

    @pytest.mark.asyncio
    async def test_rename_folder(self, client: AsyncClient, db_session: AsyncSession):
        _, token = await _create_user(db_session)
        fid = await _create_folder(client, token, "OldName")
        resp = await client.post(f"/api/v1/folders/{fid}/rename", json={"name": "NewName"},
                                 headers=_auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "NewName"


class TestRepositoryQueries:
    @pytest.mark.asyncio
    async def test_subtree_ids_includes_children(self, db_session: AsyncSession):
        repo = FolderRepository(db_session)
        user_id = uuid.uuid4()
        root = await repo.create("Root", owner_id=user_id)
        child = await repo.create("Child", owner_id=user_id, parent_id=root.id)
        sub = await repo.create("Sub", owner_id=user_id, parent_id=child.id)
        ids = await repo.get_subtree_ids(root.id)
        assert root.id in ids
        assert child.id in ids
        assert sub.id in ids

    @pytest.mark.asyncio
    async def test_is_ancestor_detects_ancestor(self, db_session: AsyncSession):
        repo = FolderRepository(db_session)
        user_id = uuid.uuid4()
        a = await repo.create("A", owner_id=user_id)
        b = await repo.create("B", owner_id=user_id, parent_id=a.id)
        c = await repo.create("C", owner_id=user_id, parent_id=b.id)
        assert await repo.is_ancestor(a.id, c.id) is True
        assert await repo.is_ancestor(b.id, c.id) is True
        assert await repo.is_ancestor(c.id, a.id) is False

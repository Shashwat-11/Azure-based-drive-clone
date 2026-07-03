from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import auth, create_folder


class TestFoldersE2E:
    @pytest.mark.asyncio
    async def test_create_and_list_folders(self, client: AsyncClient, owner):
        _, token = owner
        await create_folder(client, token, "Documents")
        await create_folder(client, token, "Photos")

        resp = await client.get("/api/v1/folders", headers=auth(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2

    @pytest.mark.asyncio
    async def test_nested_folder_hierarchy(self, client: AsyncClient, owner):
        _, token = owner
        root = await create_folder(client, token, "Home")
        child = await create_folder(client, token, "SubFolder", parent_id=root["id"])
        await create_folder(client, token, "Deep", parent_id=child["id"])

        resp = await client.get(f"/api/v1/folders?parent_id={child['id']}", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["folders"][0]["name"] == "Deep"

    @pytest.mark.asyncio
    async def test_rename_folder(self, client: AsyncClient, owner):
        _, token = owner
        f = await create_folder(client, token, "OldName")

        resp = await client.post(
            f"/api/v1/folders/{f['id']}/rename",
            json={"name": "NewName"}, headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "NewName"

    @pytest.mark.asyncio
    async def test_move_folder(self, client: AsyncClient, owner):
        _, token = owner
        src = await create_folder(client, token, "Source")
        dst = await create_folder(client, token, "Dest")

        resp = await client.post(
            f"/api/v1/folders/{src['id']}/move",
            json={"target_parent_id": dst["id"]}, headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["parent_id"] == dst["id"]

    @pytest.mark.asyncio
    async def test_delete_folder_soft(self, client: AsyncClient, owner):
        _, token = owner
        f = await create_folder(client, token, "ToDelete")

        resp = await client.delete(f"/api/v1/folders/{f['id']}", headers=auth(token))
        assert resp.status_code == 200

        # Should not appear in listings
        listing = await client.get("/api/v1/folders", headers=auth(token))
        assert listing.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_breadcrumbs(self, client: AsyncClient, owner):
        _, token = owner
        root = await create_folder(client, token, "Home")
        child = await create_folder(client, token, "Docs", parent_id=root["id"])

        resp = await client.get(f"/api/v1/folders/{child['id']}/breadcrumbs", headers=auth(token))
        assert resp.status_code == 200
        crumbs = resp.json()["breadcrumbs"]
        names = [c["name"] for c in crumbs]
        assert "Home" in names
        assert "Docs" in names

    @pytest.mark.asyncio
    async def test_folder_size(self, client: AsyncClient, owner):
        from tests.e2e.conftest import upload_file

        _, token = owner
        f = await create_folder(client, token, "Data")
        await upload_file(client, token, name="a.txt", content=b"12345", folder_id=f["id"])
        await upload_file(client, token, name="b.txt", content=b"abcde", folder_id=f["id"])

        resp = await client.get(f"/api/v1/folders/{f['id']}/size", headers=auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["file_count"] == 2
        assert data["total_size_bytes"] == 10

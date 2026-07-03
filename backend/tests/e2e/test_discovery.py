from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import auth, upload_file


class TestSearchE2E:
    @pytest.mark.asyncio
    async def test_filename_search(self, client: AsyncClient, owner):
        _, token = owner
        await upload_file(client, token, name="report_2024.pdf")
        await upload_file(client, token, name="notes_2024.txt")

        resp = await client.get("/api/v1/search?query=report", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_extension_filter(self, client: AsyncClient, owner):
        _, token = owner
        await upload_file(client, token, name="doc1.pdf")
        await upload_file(client, token, name="doc2.pdf")
        await upload_file(client, token, name="notes.txt")

        resp = await client.get("/api/v1/search?extension=pdf", headers=auth(token))
        assert resp.status_code == 200
        for f in resp.json()["files"]:
            assert f["extension"] == "pdf"

    @pytest.mark.asyncio
    async def test_tag_search(self, client: AsyncClient, owner):
        _, token = owner
        f = await upload_file(client, token, name="tagged_file.txt")

        tag_resp = await client.post("/api/v1/tags", json={"name": "important"},
                                     headers=auth(token))
        tag_id = tag_resp.json()["id"]
        await client.post(f"/api/v1/files/{f['id']}/tags", json={"tag_id": tag_id},
                          headers=auth(token))

        resp = await client.get(f"/api/v1/search?tag_id={tag_id}", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_search_suggestions(self, client: AsyncClient, owner):
        _, token = owner
        await upload_file(client, token, name="budget_2024.xlsx")
        await upload_file(client, token, name="budget_2025.xlsx")

        resp = await client.get(
            "/api/v1/search/suggestions?query=budget", headers=auth(token))
        assert resp.status_code == 200
        assert len(resp.json()["suggestions"]) >= 1


class TestDiscoveryE2E:
    @pytest.mark.asyncio
    async def test_tags_lifecycle(self, client: AsyncClient, owner):
        _, token = owner
        t = await client.post("/api/v1/tags", json={"name": "work"}, headers=auth(token))
        assert t.status_code == 201

        tags = await client.get("/api/v1/tags", headers=auth(token))
        assert tags.status_code == 200
        assert len(tags.json()) >= 1

        f = await upload_file(client, token)
        await client.post(
            f"/api/v1/files/{f['id']}/tags",
            json={"tag_id": t.json()["id"]}, headers=auth(token),
        )
        # Remove tag
        await client.delete(
            f"/api/v1/files/{f['id']}/tags/{t.json()['id']}", headers=auth(token))

        # Delete tag
        await client.delete(f"/api/v1/tags/{t.json()['id']}", headers=auth(token))

    @pytest.mark.asyncio
    async def test_favorites(self, client: AsyncClient, owner):
        _, token = owner
        f = await upload_file(client, token, name="favorite_me.txt")

        fav = await client.post(f"/api/v1/favorites/{f['id']}", headers=auth(token))
        assert fav.status_code == 201

        flist = await client.get("/api/v1/favorites", headers=auth(token))
        assert flist.status_code == 200
        assert flist.json()["total"] >= 1

        await client.delete(f"/api/v1/favorites/{f['id']}", headers=auth(token))
        flist2 = await client.get("/api/v1/favorites", headers=auth(token))
        assert flist2.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_recent_files(self, client: AsyncClient, owner):
        _, token = owner
        await upload_file(client, token, name="recent_test.txt")

        resp = await client.get("/api/v1/recent", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_file_metadata(self, client: AsyncClient, owner):
        _, token = owner
        f = await upload_file(client, token)

        resp = await client.patch(
            f"/api/v1/files/{f['id']}/metadata",
            json={"description": "My document", "color_label": "green"},
            headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "My document"

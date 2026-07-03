from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import auth, create_folder, upload_file


class TestFilesE2E:
    @pytest.mark.asyncio
    async def test_upload_and_download(self, client: AsyncClient, owner):
        _, token = owner
        content = b"End-to-end test content verification"

        f = await upload_file(client, token, name="verify.txt", content=content)

        assert f["original_filename"] == "verify.txt"
        assert f["file_size_bytes"] == len(content)
        assert f["checksum_sha256"] is not None
        assert f["version_number"] == 1

        # Download and verify
        resp = await client.get(f"/api/v1/files/{f['id']}/download", headers=auth(token))
        assert resp.status_code == 200
        assert resp.content == content
        assert resp.headers.get("Content-Length") == str(len(content))
        assert "X-Checksum-SHA256" in resp.headers

    @pytest.mark.asyncio
    async def test_duplicate_upload_creates_new_version(self, client: AsyncClient, owner):
        _, token = owner
        f1 = await upload_file(client, token, name="version_test.txt", content=b"v1 content")
        assert f1["version_number"] == 1

        f2 = await upload_file(client, token, name="version_test.txt", content=b"v2 content")
        assert f2["version_number"] == 2
        assert f2["id"] == f1["id"]  # Same file, not a new one

        # Verify version history
        versions = await client.get(
            f"/api/v1/versions/file/{f2['id']}", headers=auth(token))
        assert versions.status_code == 200
        assert versions.json()["total"] == 2

    @pytest.mark.asyncio
    async def test_restore_previous_version(self, client: AsyncClient, owner):
        _, token = owner
        await upload_file(client, token, name="restore_test.txt", content=b"original")
        f2 = await upload_file(client, token, name="restore_test.txt", content=b"modified")

        # Find v1
        versions = await client.get(
            f"/api/v1/versions/file/{f2['id']}", headers=auth(token))
        v1 = [v for v in versions.json()["versions"] if v["version_number"] == 1][0]

        # Restore v1
        restore = await client.post(
            f"/api/v1/versions/{v1['id']}/restore", headers=auth(token))
        assert restore.status_code == 200
        assert restore.json()["version_number"] >= 3

        # Download current version — should be original content
        dl = await client.get(f"/api/v1/files/{f2['id']}/download", headers=auth(token))
        assert dl.content == b"original"

    @pytest.mark.asyncio
    async def test_rename_file(self, client: AsyncClient, owner):
        _, token = owner
        f = await upload_file(client, token, name="old_name.txt")

        resp = await client.post(
            f"/api/v1/files/{f['id']}/rename",
            json={"name": "new_name.txt"}, headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["original_filename"] == "new_name.txt"

    @pytest.mark.asyncio
    async def test_move_file(self, client: AsyncClient, owner):
        _, token = owner
        src = await create_folder(client, token, "Src")
        dst = await create_folder(client, token, "Dst")
        f = await upload_file(client, token, name="moveme.txt", folder_id=src["id"])

        resp = await client.post(
            f"/api/v1/files/{f['id']}/move",
            json={"target_parent_id": dst["id"]}, headers=auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["folder_id"] == dst["id"]

    @pytest.mark.asyncio
    async def test_soft_delete_file(self, client: AsyncClient, owner):
        _, token = owner
        f = await upload_file(client, token, name="delete_me.txt")

        resp = await client.delete(f"/api/v1/files/{f['id']}", headers=auth(token))
        assert resp.status_code == 200

        # Should be gone from listing
        get_resp = await client.get(f"/api/v1/files/{f['id']}", headers=auth(token))
        assert get_resp.status_code == 404

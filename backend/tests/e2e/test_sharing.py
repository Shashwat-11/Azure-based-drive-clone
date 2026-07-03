from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import auth, upload_file


class TestSharingE2E:
    @pytest.mark.asyncio
    async def test_share_and_access(self, client: AsyncClient, owner, collab):
        _, owner_token = owner
        collab_id, collab_token = collab
        f = await upload_file(client, owner_token, name="shared_doc.txt")

        resp = await client.post(
            f"/api/v1/collaboration/share/file/{f['id']}",
            json={"user_id": str(collab_id), "role": "viewer"},
            headers=auth(owner_token),
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "viewer"

        # Collaborator can read
        get_resp = await client.get(f"/api/v1/files/{f['id']}", headers=auth(collab_token))
        assert get_resp.status_code == 200
        assert get_resp.json()["original_filename"] == "shared_doc.txt"

    @pytest.mark.asyncio
    async def test_viewer_cannot_modify(self, client: AsyncClient, owner, collab):
        _, owner_token = owner
        collab_id, collab_token = collab
        f = await upload_file(client, owner_token, name="readonly.txt")
        await client.post(
            f"/api/v1/collaboration/share/file/{f['id']}",
            json={"user_id": str(collab_id), "role": "viewer"},
            headers=auth(owner_token),
        )

        # Viewer cannot delete
        del_resp = await client.delete(f"/api/v1/files/{f['id']}", headers=auth(collab_token))
        assert del_resp.status_code in (403, 404)

        # Viewer cannot rename
        ren_resp = await client.post(
            f"/api/v1/files/{f['id']}/rename",
            json={"name": "renamed.txt"}, headers=auth(collab_token),
        )
        assert ren_resp.status_code in (403, 404)

    @pytest.mark.asyncio
    async def test_editor_can_modify(self, client: AsyncClient, owner, collab):
        _, owner_token = owner
        collab_id, collab_token = collab
        f = await upload_file(client, owner_token, name="editable.txt")
        await client.post(
            f"/api/v1/collaboration/share/file/{f['id']}",
            json={"user_id": str(collab_id), "role": "editor"},
            headers=auth(owner_token),
        )

        # Editor can rename
        ren_resp = await client.post(
            f"/api/v1/files/{f['id']}/rename",
            json={"name": "editor_renamed.txt"}, headers=auth(collab_token),
        )
        assert ren_resp.status_code == 200

    @pytest.mark.asyncio
    async def test_shared_with_me(self, client: AsyncClient, owner, collab):
        _, owner_token = owner
        collab_id, collab_token = collab
        f = await upload_file(client, owner_token)
        await client.post(
            f"/api/v1/collaboration/share/file/{f['id']}",
            json={"user_id": str(collab_id), "role": "editor"},
            headers=auth(owner_token),
        )

        resp = await client.get("/api/v1/collaboration/shared-with-me", headers=auth(collab_token))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_create_shared_link(self, client: AsyncClient, owner):
        _, token = owner
        f = await upload_file(client, token, name="link_me.txt")

        link = await client.post(
            "/api/v1/collaboration/links",
            json={"resource_type": "file", "resource_id": f["id"], "is_public": True},
            headers=auth(token),
        )
        assert link.status_code == 201
        assert "token" in link.json()
        assert link.json()["is_public"] is True

    @pytest.mark.asyncio
    async def test_private_shared_link(self, client: AsyncClient, owner):
        _, token = owner
        f = await upload_file(client, token, name="private_link.txt")

        link = await client.post(
            "/api/v1/collaboration/links",
            json={"resource_type": "file", "resource_id": f["id"], "is_public": False},
            headers=auth(token),
        )
        assert link.status_code == 201
        assert link.json()["is_public"] is False

    @pytest.mark.asyncio
    async def test_transfer_ownership(self, client: AsyncClient, owner, collab):
        _, owner_token = owner
        new_owner_id, _ = collab
        f = await upload_file(client, owner_token)

        resp = await client.post(
            f"/api/v1/collaboration/transfer-ownership/file/{f['id']}",
            json={"new_owner_id": str(new_owner_id)},
            headers=auth(owner_token),
        )
        assert resp.status_code == 200

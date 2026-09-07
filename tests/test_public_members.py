import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.mark.asyncio
async def test_public_member_count():
    """Verify that GET /orion/api/v1/members/count is public (200 OK without token)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/orion/api/v1/members/count")
        assert response.status_code == 200
        data = response.json()
        assert "total_members" in data
        assert "active_members" in data
        assert "alumni_count" in data
        assert isinstance(data["total_members"], int)
        assert data["total_members"] >= 0


@pytest.mark.asyncio
async def test_members_list_requires_auth():
    """Verify that GET /orion/api/v1/members/ still requires auth (401 without token)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/orion/api/v1/members/")
        assert response.status_code == 401

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.mark.asyncio
async def test_auth_login_superadmin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/orion/api/v1/auth/login",
            json={"student_id": "2210511084", "password": "OrionAdmin#2026!"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["full_name"] == "Dzulfikri Adjmal"
        assert data["user"]["role"] == "SUPERADMIN"
        assert data["user"]["student_id"] == "2210511084"


@pytest.mark.asyncio
async def test_auth_login_invalid_password():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/orion/api/v1/auth/login",
            json={"student_id": "2210511084", "password": "wrongpassword"},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_get_me_and_update_profile():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Login
        login_res = await ac.post(
            "/orion/api/v1/auth/login",
            json={"student_id": "2210511084", "password": "OrionAdmin#2026!"},
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # GET /auth/me
        me_res = await ac.get("/orion/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["student_id"] == "2210511084"

        # PUT /auth/me
        update_res = await ac.put(
            "/orion/api/v1/auth/me",
            headers=headers,
            json={"full_name": "Dzulfikri Adjmal", "avatar": "https://api.dicebear.com/7.x/bottts/svg?seed=admin"},
        )
        assert update_res.status_code == 200
        assert update_res.json()["avatar"] == "https://api.dicebear.com/7.x/bottts/svg?seed=admin"

import pytest
from httpx import ASGITransport, AsyncClient

from config.db import engine
from main import app


@pytest.fixture(autouse=True)
async def cleanup():
    yield
    await engine.dispose()

@pytest.mark.asyncio
async def test_auth_login_superadmin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/orion/api/v1/auth/login",
            json={"student_id": "2210511084", "password": "aiotupnvj2026"}
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
            json={"student_id": "2210511084", "password": "wrongpassword"}
        )
        assert response.status_code == 401

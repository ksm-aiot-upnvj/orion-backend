"""Regression tests for the server-side password policy and profile validation."""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from config.config import settings
from config.db import engine
from main import app
from schemas.auth import ChangePasswordRequest, ProfileUpdate
from schemas.member import GrantERPAccessRequest, ResetMemberPasswordRequest

API = "/orion/api/v1"


@pytest.fixture(autouse=True)
async def cleanup():
    yield
    await engine.dispose()


@pytest.mark.parametrize("pw", ["", "short", "1234567", "é" * 37])  # "é"*37 = 74 bytes > bcrypt's 72
def test_weak_or_oversized_passwords_rejected(pw):
    with pytest.raises(ValidationError):
        ChangePasswordRequest(current_password="x", new_password=pw)
    with pytest.raises(ValidationError):
        ResetMemberPasswordRequest(new_password=pw)
    with pytest.raises(ValidationError):
        GrantERPAccessRequest(password=pw)


def test_valid_password_accepted():
    assert ResetMemberPasswordRequest(new_password="Valid#Pass2026").new_password == "Valid#Pass2026"


def test_erp_role_restricted():
    with pytest.raises(ValidationError):
        GrantERPAccessRequest(password="Valid#Pass2026", role="GOD")


def test_profile_email_must_be_valid():
    with pytest.raises(ValidationError):
        ProfileUpdate(email="not-an-email")
    with pytest.raises(ValidationError):
        ProfileUpdate(full_name="x" * 151)


@pytest.mark.asyncio
async def test_long_password_is_422_not_500():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        login = await ac.post(
            f"{API}/auth/login", json={"student_id": settings.SUPERADMIN_NIM, "password": settings.SUPERADMIN_PW}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        res = await ac.put(
            f"{API}/auth/me/password",
            headers=headers,
            json={"current_password": settings.SUPERADMIN_PW, "new_password": "x" * 100},
        )
    assert res.status_code == 422

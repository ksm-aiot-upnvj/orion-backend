"""Regression tests for JWT handling."""

from datetime import timedelta

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from config.config import settings
from config.db import engine
from main import app
from utils.security import create_access_token, create_refresh_token, decode_access_token, decode_refresh_token

API = "/orion/api/v1"


@pytest.fixture(autouse=True)
async def cleanup():
    yield
    await engine.dispose()


def test_refresh_token_is_not_an_access_token():
    refresh = create_refresh_token({"sub": "0190a1b2-c3d4-7e5f-8a6b-7c8d9e0f1a2b"})
    assert decode_access_token(refresh) is None
    assert decode_refresh_token(refresh) is not None


def test_access_token_is_not_a_refresh_token():
    access = create_access_token({"sub": "0190a1b2-c3d4-7e5f-8a6b-7c8d9e0f1a2b"})
    assert decode_refresh_token(access) is None
    assert decode_access_token(access) is not None


def test_tokens_without_expiry_or_type_are_rejected():
    no_exp = jwt.encode({"sub": "x", "type": "access"}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    no_type = jwt.encode({"sub": "x", "exp": 9999999999}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    assert decode_access_token(no_exp) is None
    assert decode_access_token(no_type) is None


def test_alg_none_and_wrong_key_are_rejected():
    unsigned = jwt.encode({"sub": "x", "type": "access", "exp": 9999999999}, key=None, algorithm="none")
    forged = jwt.encode({"sub": "x", "type": "access", "exp": 9999999999}, "attacker-chosen-secret-0123456789abcdef", algorithm="HS256")
    assert decode_access_token(unsigned) is None
    assert decode_access_token(forged) is None


def test_expired_access_token_is_rejected():
    expired = create_access_token({"sub": "x"}, expires_delta=timedelta(seconds=-5))
    assert decode_access_token(expired) is None


@pytest.mark.asyncio
async def test_refresh_token_cannot_call_protected_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        login = await ac.post(
            f"{API}/auth/login", json={"student_id": settings.SUPERADMIN_NIM, "password": settings.SUPERADMIN_PW}
        )
        refresh = login.json()["refresh_token"]
        res = await ac.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {refresh}"})
    assert res.status_code == 401

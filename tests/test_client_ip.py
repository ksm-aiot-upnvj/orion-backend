"""Regression tests: client IP resolution must not trust client-controlled X-Forwarded-For entries."""

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from config.config import settings
from config.db import engine
from main import app
from utils.client_ip import get_client_ip


@pytest.fixture(autouse=True)
async def cleanup():
    yield
    await engine.dispose()


def _request(xff: str | None, peer: str = "10.0.0.5") -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff is not None else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


def test_uses_entry_appended_by_trusted_proxy(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    # attacker sent "6.6.6.6", our proxy appended the real address
    assert get_client_ip(_request("6.6.6.6, 203.0.113.7")) == "203.0.113.7"


def test_zero_hops_ignores_header(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 0)
    assert get_client_ip(_request("6.6.6.6")) == "10.0.0.5"


def test_invalid_or_oversized_values_fall_back_to_peer(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    assert get_client_ip(_request("A" * 300)) == "10.0.0.5"
    assert get_client_ip(_request("1.2.3.4'); DROP TABLE users;--")) == "10.0.0.5"
    assert get_client_ip(_request(None)) == "10.0.0.5"


@pytest.mark.asyncio
async def test_login_rate_limit_not_bypassed_by_rotating_forwarded_for(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 0)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        statuses = []
        for i in range(6):
            res = await ac.post(
                "/orion/api/v1/auth/login",
                json={"student_id": "0000000000", "password": "wrong-password"},
                headers={"X-Forwarded-For": f"198.51.100.{i}"},
            )
            statuses.append(res.status_code)
    assert statuses[:5] == [401] * 5
    assert statuses[5] == 429

"""Old (pre clean-URL refactor) API paths must permanently redirect to their replacements."""

import pytest
from httpx import ASGITransport, AsyncClient

from config.db import engine
from main import app

PREFIX = "/orion/api/v1"


@pytest.fixture(autouse=True)
async def cleanup():
    yield
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "old", "new", "expected_status"),
    [
        ("GET", "/members/", "/members", 301),
        ("POST", "/members/", "/members", 308),
        ("GET", "/members/count", "/members/stats", 301),
        ("GET", "/members/public/organization", "/members/public", 301),
        ("POST", "/members/import-excel", "/members/imports", 308),
        ("POST", "/members/2410511001/reset-password", "/members/2410511001/password", 308),
        ("GET", "/registrations/", "/registrations", 301),
        ("POST", "/registrations/", "/registrations", 308),
        ("GET", "/audit-logs/", "/audit-logs", 301),
        ("POST", "/auth/change-password", "/auth/me/password", 308),
        ("POST", "/uploads/avatar", "/uploads/avatars", 308),
        ("POST", "/uploads/cv", "/uploads/cvs", 308),
        ("GET", "/avatars/abc.webp", "/uploads/avatars/abc.webp", 301),
        ("GET", "/cvs/abc.pdf", "/uploads/cvs/abc.pdf", 301),
        ("GET", "/db-test", "/health/db", 301),
    ],
)
async def test_legacy_url_redirects(method, old, new, expected_status):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.request(method, f"{PREFIX}{old}", follow_redirects=False)
    assert response.status_code == expected_status
    assert response.headers["location"] == f"{PREFIX}{new}"


@pytest.mark.asyncio
async def test_legacy_redirect_preserves_query_string():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"{PREFIX}/audit-logs/?limit=10&offset=20", follow_redirects=False)
    assert response.status_code == 301
    assert response.headers["location"] == f"{PREFIX}/audit-logs?limit=10&offset=20"


@pytest.mark.asyncio
async def test_legacy_redirect_encodes_path_params():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(f"{PREFIX}/members/a%3Fb/reset-password", follow_redirects=False)
    assert response.headers["location"] == f"{PREFIX}/members/a%3Fb/password"


@pytest.mark.asyncio
async def test_legacy_public_stats_redirect_is_followable():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"{PREFIX}/members/count", follow_redirects=True)
    assert response.status_code == 200
    assert "total_members" in response.json()


@pytest.mark.asyncio
async def test_new_routes_have_no_trailing_slash_in_schema():
    paths = app.openapi()["paths"].keys()
    assert all(not p.endswith("/") or p == "/" for p in paths), [p for p in paths if p.endswith("/")]
    for removed in ("/members/count", "/members/import-excel", "/auth/change-password", "/uploads/avatar"):
        assert removed not in paths

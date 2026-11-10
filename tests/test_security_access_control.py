"""Regression tests for privilege-escalation fixes in member / ERP-access management."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from config.config import settings
from config.db import AsyncSessionLocal, engine
from main import app

API = "/orion/api/v1"
MANAGER_NIM = "2410511901"
TARGET_NIM = "2410511902"
SUPER_TARGET_NIM = "2410511903"
MANAGER_PW = "Manager&Pass<2026>"  # contains HTML-special characters on purpose
TEST_NIMS = [MANAGER_NIM, TARGET_NIM, SUPER_TARGET_NIM]


def _member(nim: str, **extra) -> dict:
    return {
        "student_id": nim,
        "full_name": f"RBAC Test {nim}",
        "program_of_study": "S1 Informatika",
        "email": f"test_rbac_{nim}@upnvj.ac.id",
        "division": "PSDM",
        "role": "Staff",
        "intake_period": "2026",
        "status": "Aktif",
        **extra,
    }


@pytest.fixture(autouse=True)
async def cleanup_test_accounts():
    yield
    async with AsyncSessionLocal() as session:
        await session.execute(text("DELETE FROM users WHERE student_id = ANY(:ids)"), {"ids": TEST_NIMS})
        await session.execute(text("DELETE FROM members WHERE student_id = ANY(:ids)"), {"ids": TEST_NIMS})
        await session.commit()
    await engine.dispose()


async def _login(ac: AsyncClient, nim: str, password: str) -> dict:
    res = await ac.post(f"{API}/auth/login", json={"student_id": nim, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.mark.asyncio
async def test_member_manager_cannot_escalate_privileges():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        admin = await _login(ac, settings.SUPERADMIN_NIM, settings.SUPERADMIN_PW)

        # A PSDM staff member with ERP access is a legitimate member manager (can_manage_members)
        res = await ac.post(
            f"{API}/members",
            headers=admin,
            json=_member(MANAGER_NIM, create_erp_account=True, erp_password=MANAGER_PW, erp_role="PENGURUS"),
        )
        assert res.status_code == 201, res.text
        assert (await ac.post(f"{API}/members", headers=admin, json=_member(TARGET_NIM))).status_code == 201
        res = await ac.post(
            f"{API}/members",
            headers=admin,
            json=_member(SUPER_TARGET_NIM, create_erp_account=True, erp_password="SuperTarget#2026", erp_role="SUPERADMIN"),
        )
        assert res.status_code == 201, res.text

        # Password with HTML-special characters is stored as typed (was hashed HTML-escaped before)
        manager = await _login(ac, MANAGER_NIM, MANAGER_PW)

        # Grant SUPERADMIN to someone else -> denied
        res = await ac.post(f"{API}/members/{TARGET_NIM}/access", headers=manager, json={"password": "Whatever#2026", "role": "SUPERADMIN"})
        assert res.status_code == 403
        # ... also through member create/update ERP flags
        res = await ac.put(
            f"{API}/members/{TARGET_NIM}",
            headers=manager,
            json={"create_erp_account": True, "erp_password": "Whatever#2026", "erp_role": "SUPERADMIN"},
        )
        assert res.status_code == 403

        # Change own ERP account / own role -> denied
        res = await ac.post(f"{API}/members/{MANAGER_NIM}/access", headers=manager, json={"password": "Whatever#2026", "role": "PENGURUS"})
        assert res.status_code == 403
        res = await ac.put(f"{API}/members/{MANAGER_NIM}", headers=manager, json={"role": "Ketua"})
        assert res.status_code == 403
        # Non-privileged self edits still work
        res = await ac.put(f"{API}/members/{MANAGER_NIM}", headers=manager, json={"discord_id": "rbac-test"})
        assert res.status_code == 200

        # Take over a superadmin account -> denied
        res = await ac.put(f"{API}/members/{SUPER_TARGET_NIM}/password", headers=manager, json={"new_password": "Hijacked#2026"})
        assert res.status_code == 403
        res = await ac.delete(f"{API}/members/{SUPER_TARGET_NIM}/access", headers=manager)
        assert res.status_code == 403

        # Unknown ERP role -> rejected
        res = await ac.post(f"{API}/members/{TARGET_NIM}/access", headers=admin, json={"password": "Whatever#2026", "role": "GOD"})
        assert res.status_code in (400, 422)

        # Legitimate manager operation still works
        res = await ac.post(f"{API}/members/{TARGET_NIM}/access", headers=manager, json={"password": "Target#2026pw", "role": "PENGURUS"})
        assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_alumni_superadmin_keeps_access_until_explicit_revoke():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        admin = await _login(ac, settings.SUPERADMIN_NIM, settings.SUPERADMIN_PW)
        password = "AlumniSuper#2026"
        credentials = {"student_id": SUPER_TARGET_NIM, "password": password}
        create = await ac.post(
            f"{API}/members",
            headers=admin,
            json=_member(SUPER_TARGET_NIM, create_erp_account=True, erp_password=password, erp_role="SUPERADMIN"),
        )
        assert create.status_code == 201, create.text

        incompatible_update = await ac.put(
            f"{API}/members/{SUPER_TARGET_NIM}",
            headers=admin,
            json={"status": "Alumni", "create_erp_account": True, "erp_password": password, "erp_role": "PENGURUS"},
        )
        assert incompatible_update.status_code == 409
        member = await ac.get(f"{API}/members/{SUPER_TARGET_NIM}", headers=admin)
        assert member.json()["status"] == "Aktif"

        update = await ac.put(f"{API}/members/{SUPER_TARGET_NIM}", headers=admin, json={"status": "Alumni"})
        assert update.status_code == 200, update.text
        assert update.json()["has_erp_access"] is True
        profile = await ac.get(f"{API}/members/{SUPER_TARGET_NIM}/alumni-profile", headers=admin)
        assert profile.status_code == 200
        assert profile.json()["visibility"] is False

        login = await ac.post(f"{API}/auth/login", json=credentials)
        assert login.status_code == 200, login.text
        assert login.json()["user"]["is_superadmin"] is True
        alumni_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert (await ac.get(f"{API}/auth/session", headers=alumni_headers)).status_code == 200

        revoke = await ac.delete(f"{API}/members/{SUPER_TARGET_NIM}/access", headers=admin)
        assert revoke.status_code == 200
        assert (await ac.get(f"{API}/auth/session", headers=alumni_headers)).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["MEMBER", "Anggota", "ANGGOTA", "", None, "Guest", "user"])
async def test_require_pengurus_denies_non_pengurus_roles(role):
    from fastapi import HTTPException

    from utils.auth_deps import require_pengurus

    with pytest.raises(HTTPException) as exc:
        await require_pengurus({"role": role, "is_superadmin": False})
    assert exc.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["Ketua", "Wakil Ketua", "Sekretaris", "Bendahara", "Kepala Divisi", "Staff", "PENGURUS"])
async def test_require_pengurus_allows_pengurus_roles(role):
    from utils.auth_deps import require_pengurus

    user = {"role": role, "is_superadmin": False}
    assert await require_pengurus(user) is user

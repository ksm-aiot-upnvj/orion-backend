"""Regression tests: the Excel member import must not create guessable logins or grant superadmin."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from config.db import AsyncSessionLocal, engine
from main import app
from utils.excel_importer import ExcelMemberImporter

KETUA_NIM = "2410511911"
STAFF_NIM = "2410511912"


def _row(nim: str, role: str, division: str | None = "PSDM") -> dict:
    return {
        "student_id": nim,
        "full_name": f"Import Test {nim}",
        "program_of_study": "S1 Informatika",
        "semester": 3,
        "email": f"test_rbac_import_{nim}@upnvj.ac.id",
        "contact_info": None,
        "domicile_city": None,
        "division": division,
        "role": role,
        "intake_period": "2026",
        "interest_track": ["AI"],
        "focus_expertise": None,
        "exploration_field": None,
        "field_reason": None,
        "programming_languages": None,
        "tools_frameworks": None,
        "project_experience": None,
        "hackathon_experience": None,
        "portfolio_url": None,
        "routine_commitment": None,
        "weekly_free_time": None,
        "other_activities": None,
        "discord_id": None,
        "registration_timestamp": None,
        "status": "Aktif",
        "join_date": "15/01/2026",
    }


@pytest.fixture(autouse=True)
async def cleanup_import_rows():
    yield
    async with AsyncSessionLocal() as session:
        ids = [KETUA_NIM, STAFF_NIM]
        await session.execute(text("DELETE FROM users WHERE student_id = ANY(:ids)"), {"ids": ids})
        await session.execute(text("DELETE FROM members WHERE student_id = ANY(:ids)"), {"ids": ids})
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_import_does_not_grant_superadmin_or_known_password(monkeypatch):
    import utils.excel_importer as importer

    monkeypatch.setattr(importer.settings, "IMPORT_DEFAULT_PASSWORD", None)
    used_passwords = []
    real_hash = importer.hash_password
    monkeypatch.setattr(importer, "hash_password", lambda pw: used_passwords.append(pw) or real_hash(pw))
    async with AsyncSessionLocal() as session:
        await ExcelMemberImporter.import_to_database(session, [_row(KETUA_NIM, "Ketua", "BPH"), _row(STAFF_NIM, "Staff")])
        await ExcelMemberImporter.import_to_database(session, [_row(STAFF_NIM, "Staff")])
        res = await session.execute(
            text("SELECT student_id, is_superadmin FROM users WHERE student_id = ANY(:ids)"),
            {"ids": [KETUA_NIM, STAFF_NIM]},
        )
        flags = {r["student_id"]: r["is_superadmin"] for r in res.mappings().all()}
    assert flags == {KETUA_NIM: False, STAFF_NIM: False}
    # Without IMPORT_DEFAULT_PASSWORD every import uses a fresh unguessable password (no shared constant)
    assert len(used_passwords) == 2 and used_passwords[0] != used_passwords[1]
    assert all(len(pw) >= 32 for pw in used_passwords)


@pytest.mark.asyncio
async def test_import_cannot_change_importers_own_role():
    async with AsyncSessionLocal() as session:
        await ExcelMemberImporter.import_to_database(session, [_row(STAFF_NIM, "Staff")])
        actor = {"student_id": STAFF_NIM, "role": "Staff", "is_superadmin": False}
        await ExcelMemberImporter.import_to_database(session, [_row(STAFF_NIM, "Ketua", "BPH")], actor=actor)
        res = await session.execute(text("SELECT role, division FROM members WHERE student_id = :s"), {"s": STAFF_NIM})
        row = res.mappings().one()
    assert (row["role"], row["division"]) == ("Staff", "PSDM")


@pytest.mark.asyncio
async def test_import_escapes_html_and_drops_script_links():
    row = _row(STAFF_NIM, "Staff")
    row["full_name"] = '<img src=x onerror="alert(1)">'
    row["project_experience"] = "<script>steal()</script>"
    row["portfolio_url"] = "javascript:alert(document.domain)"
    async with AsyncSessionLocal() as session:
        await ExcelMemberImporter.import_to_database(session, [row])
        res = await session.execute(
            text("SELECT full_name, project_experience, portfolio_url FROM members WHERE student_id = :s"),
            {"s": STAFF_NIM},
        )
        stored = res.mappings().one()
    assert "<" not in stored["full_name"] and "<" not in stored["project_experience"]
    assert stored["portfolio_url"] is None


@pytest.mark.asyncio
async def test_import_endpoint_rejects_oversized_and_garbage_files_without_leaking():
    from config.config import settings

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        login = await ac.post(
            "/orion/api/v1/auth/login", json={"student_id": settings.SUPERADMIN_NIM, "password": settings.SUPERADMIN_PW}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        big = ("big.xlsx", b"0" * (5 * 1024 * 1024 + 1), "application/octet-stream")
        res = await ac.post("/orion/api/v1/members/imports", headers=headers, files={"file": big})
        assert res.status_code == 413
        garbage = ("bad.xlsx", b"PK\x03\x04 not really a workbook", "application/octet-stream")
        res = await ac.post("/orion/api/v1/members/imports", headers=headers, files={"file": garbage})
        assert res.status_code == 400
        assert "Traceback" not in res.text and "zipfile" not in res.text.lower()
        res = await ac.post("/orion/api/v1/members/imports", headers=headers, files={"file": ("a.xls", b"x", "x")})
        assert res.status_code == 400


def test_openpyxl_uses_defusedxml():
    import openpyxl.xml

    assert openpyxl.xml.DEFUSEDXML is True

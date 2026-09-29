"""Regression tests: approving a registration must not reuse a deleted member ID or ignore the year."""

import pytest
from sqlalchemy import text

from config.db import AsyncSessionLocal, engine
from services.member_service import MemberService
from services.registration_service import RegistrationService

YEAR = "2031"  # a year no other test uses
NIMS = ["3110511001", "3110511002", "3110511003"]


@pytest.fixture(autouse=True)
async def cleanup():
    yield
    async with AsyncSessionLocal() as session:
        await session.execute(text("DELETE FROM registrations WHERE student_id = ANY(:ids)"), {"ids": NIMS})
        await session.execute(text("DELETE FROM members WHERE student_id = ANY(:ids)"), {"ids": NIMS})
        await session.commit()
    await engine.dispose()


def _member(nim: str) -> dict:
    return {
        "student_id": nim,
        "full_name": f"MemberId Test {nim}",
        "program_of_study": "S1 Informatika",
        "email": f"test_rbac_mid_{nim}@upnvj.ac.id",
        "intake_period": YEAR,
    }


@pytest.mark.asyncio
async def test_approve_takes_next_free_id_for_the_year_after_deletions():
    async with AsyncSessionLocal() as session:
        members = MemberService(session)
        first = await members.create_member(_member(NIMS[0]))
        second = await members.create_member(_member(NIMS[1]))
        assert (first["member_id"], second["member_id"]) == (f"AIOT-{YEAR}-001", f"AIOT-{YEAR}-002")
        await members.delete_member(NIMS[0])

        regs = RegistrationService(session)
        await regs.create_registration({**_member(NIMS[2]), "consent_given": True})
        approved = await regs.approve_registration(NIMS[2], reviewer_name="Tester", reviewer_role="SUPERADMIN")

    # COUNT(*)+1 over all members produced an ID unrelated to the year's sequence and could hit an existing one
    assert approved["member_id"] == f"AIOT-{YEAR}-003"


@pytest.mark.asyncio
async def test_approve_reuses_existing_member_id():
    async with AsyncSessionLocal() as session:
        member = await MemberService(session).create_member(_member(NIMS[2]))
        regs = RegistrationService(session)
        await regs.create_registration({**_member(NIMS[2]), "consent_given": True})
        approved = await regs.approve_registration(NIMS[2], reviewer_name="Tester", reviewer_role="SUPERADMIN")
    assert approved["member_id"] == member["member_id"]

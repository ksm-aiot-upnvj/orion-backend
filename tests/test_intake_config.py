"""Regression tests: intake config is validated on write and enforced fail-closed on submit."""

import json

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import text

from config.db import AsyncSessionLocal, engine
from main import app
from schemas.registration import IntakeStatusUpdate

API = "/orion/api/v1"
GOOD_CONFIG = {"status": "OPEN", "batch_name": "Penerimaan Anggota Baru Periode 2026", "deadline": "2026-12-31", "quota": 100}


@pytest.fixture(autouse=True)
async def restore_config():
    yield
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("UPDATE system_settings SET value = :v WHERE key = 'intake_config'"), {"v": json.dumps(GOOD_CONFIG)}
        )
        await session.commit()
    await engine.dispose()


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "MAYBE", "batch_name": "b", "deadline": "2026-12-31"},
        {"status": "OPEN", "batch_name": "b", "deadline": "31/12/2026"},
        {"status": "OPEN", "batch_name": "b", "deadline": "2026-02-30"},
        {"status": "OPEN", "batch_name": "b", "deadline": "2026-12-31", "quota": -1},
        {"status": "OPEN", "batch_name": "", "deadline": "2026-12-31"},
    ],
)
def test_invalid_intake_update_rejected(payload):
    with pytest.raises(ValidationError):
        IntakeStatusUpdate(**payload)


def test_intake_update_normalizes():
    cfg = IntakeStatusUpdate(status=" closed ", batch_name="b", deadline="2026-12-31T00:00:00")
    assert (cfg.status, cfg.deadline) == ("CLOSED", "2026-12-31")


@pytest.mark.asyncio
async def test_corrupt_deadline_blocks_submission_instead_of_ignoring_it():
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("UPDATE system_settings SET value = :v WHERE key = 'intake_config'"),
            {"v": json.dumps({**GOOD_CONFIG, "deadline": "not-a-date"})},
        )
        await session.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            f"{API}/registrations",
            json={
                "student_id": "2410511999",
                "full_name": "Calon Anggota Consent Test",
                "program_of_study": "S1 Informatika",
                "email": "consent_2410511999@upnvj.ac.id",
                "intake_period": "2026",
            },
        )
    assert res.status_code == 503

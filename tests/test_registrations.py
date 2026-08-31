import pytest
from httpx import ASGITransport, AsyncClient

from config.db import Base, engine
from main import app


@pytest.mark.asyncio
async def test_registrations_crud_and_consent():
    # Ensure all tables and columns exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Login as Admin to get authorization token
        login_res = await ac.post(
            "/orion/api/v1/auth/login",
            json={"student_id": "2210511084", "password": "OrionAdmin#2026!"},
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Public submission of registration with consent
        candidate_nim = "2410511888"
        submit_res = await ac.post(
            "/orion/api/v1/registrations/",
            json={
                "student_id": candidate_nim,
                "full_name": "Calon Anggota Consent Test",
                "program_of_study": "S1 Informatika",
                "email": "consent_candidate@upnvj.ac.id",
                "intake_period": "2026",
                "interest_track": ["AI", "IoT Embedded"],
                "motivation": "Tertarik riset AIoT dan Embedded Systems",
                "consent_given": True,
            },
        )
        assert submit_res.status_code == 201
        created_data = submit_res.json()
        assert created_data["student_id"] == candidate_nim
        assert created_data["consent_given"] is True

        # 3. GET /orion/api/v1/registrations/ (must succeed without UndefinedColumnError)
        list_res = await ac.get(
            "/orion/api/v1/registrations/",
            headers=headers,
        )
        assert list_res.status_code == 200
        items = list_res.json()
        assert isinstance(items, list)
        assert len(items) >= 1

        # Check candidate in list
        found = next((item for item in items if item["student_id"] == candidate_nim), None)
        assert found is not None
        assert "consent_given" in found
        assert found["consent_given"] is True

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

        # 2. Update intake status to OPEN with future deadline
        intake_update_res = await ac.put(
            "/orion/api/v1/registrations/intake-status",
            headers=headers,
            json={
                "status": "OPEN",
                "batch_name": "Penerimaan Anggota Baru Periode 2026",
                "deadline": "2026-12-31",
                "quota": 100,
            },
        )
        assert intake_update_res.status_code == 200
        assert intake_update_res.json()["status"] == "OPEN"

        # 3. Test motivation validator: Reject if > 3 sentences
        import random
        candidate_nim = f"24{random.randint(10000000, 99999999)}"
        bad_submit_res = await ac.post(
            "/orion/api/v1/registrations/",
            json={
                "student_id": candidate_nim,
                "full_name": "Calon Anggota Exceeded",
                "program_of_study": "S1 Informatika",
                "email": f"exceeded_{candidate_nim}@upnvj.ac.id",
                "intake_period": "2026",
                "interest_track": ["AI"],
                "motivation": "Kalimat satu. Kalimat dua. Kalimat tiga. Kalimat empat yang dilarang.",
                "consent_given": True,
            },
        )
        assert bad_submit_res.status_code == 422

        # 4. Public submission of registration with valid motivation (< 3 sentences, < 100 words)
        candidate_nim_valid = f"24{random.randint(10000000, 99999999)}"
        submit_res = await ac.post(
            "/orion/api/v1/registrations/",
            json={
                "student_id": candidate_nim_valid,
                "full_name": "Calon Anggota Consent Test",
                "program_of_study": "S1 Informatika",
                "email": f"consent_{candidate_nim_valid}@upnvj.ac.id",
                "intake_period": "2026",
                "interest_track": ["AI", "IoT Embedded"],
                "motivation": "Saya tertarik bergabung dengan KSM AIoT. Ingin mempelajari riset edge computing. Siap berkontribusi aktif.",
                "consent_given": True,
            },
        )
        assert submit_res.status_code == 201
        created_data = submit_res.json()
        assert created_data["student_id"] == candidate_nim_valid
        assert created_data["consent_given"] is True

        # 5. GET /orion/api/v1/registrations/ (must succeed without UndefinedColumnError)
        list_res = await ac.get(
            "/orion/api/v1/registrations/",
            headers=headers,
        )
        assert list_res.status_code == 200
        items = list_res.json()
        assert isinstance(items, list)
        assert len(items) >= 1

        # Check candidate in list
        found = next((item for item in items if item["student_id"] == candidate_nim_valid), None)
        assert found is not None
        assert "consent_given" in found
        assert found["consent_given"] is True

        # 6. Explicit Cleanup: Delete candidate via admin endpoint to maintain zero noise in database
        del_res = await ac.delete(
            f"/orion/api/v1/registrations/{candidate_nim_valid}",
            headers=headers,
        )
        assert del_res.status_code == 200

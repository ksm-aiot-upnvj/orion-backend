import random
import pytest
from httpx import ASGITransport, AsyncClient

from config.db import Base, engine
from main import app


@pytest.mark.asyncio
async def test_bulk_delete_registrations():
    # Ensure database schema is ready
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Login as Superadmin
        login_res = await ac.post(
            "/orion/api/v1/auth/login",
            json={"student_id": "2210511084", "password": "OrionAdmin#2026!"},
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Ensure intake is OPEN with future deadline
        await ac.put(
            "/orion/api/v1/registrations/intake-status",
            headers=headers,
            json={
                "status": "OPEN",
                "batch_name": "Penerimaan Anggota Baru Periode 2026",
                "deadline": "2026-12-31",
                "quota": 100,
            },
        )

        # 2. Create 3 registrations
        nims = [f"24{random.randint(10000000, 99999999)}" for _ in range(3)]
        reg_ids = []

        for nim in nims:
            res = await ac.post(
                "/orion/api/v1/registrations/",
                json={
                    "student_id": nim,
                    "full_name": f"Candidate {nim}",
                    "program_of_study": "S1 Informatika",
                    "email": f"cand_{nim}@upnvj.ac.id",
                    "intake_period": "2026",
                    "interest_track": ["AI"],
                    "motivation": "Motivasi singkat saja.",
                    "consent_given": True,
                },
            )
            assert res.status_code == 201
            reg_ids.append(res.json()["id"])

        # 3. Test single deletion using bulk delete endpoint with 1 ID
        single_del_res = await ac.post(
            "/orion/api/v1/registrations/bulk-delete",
            headers=headers,
            json={"registration_ids": [reg_ids[0]]},
        )
        assert single_del_res.status_code == 200
        assert single_del_res.json()["deleted_count"] == 1

        # Verify reg_ids[0] is deleted
        get_res1 = await ac.get(f"/orion/api/v1/registrations/{reg_ids[0]}", headers=headers)
        assert get_res1.status_code == 404

        # 4. Test multiple deletion using bulk delete endpoint with remaining 2 IDs
        bulk_del_res = await ac.post(
            "/orion/api/v1/registrations/bulk-delete",
            headers=headers,
            json={"registration_ids": [reg_ids[1], reg_ids[2]]},
        )
        assert bulk_del_res.status_code == 200
        assert bulk_del_res.json()["deleted_count"] == 2

        # Verify reg_ids[1] and reg_ids[2] are deleted
        get_res2 = await ac.get(f"/orion/api/v1/registrations/{reg_ids[1]}", headers=headers)
        assert get_res2.status_code == 404
        get_res3 = await ac.get(f"/orion/api/v1/registrations/{reg_ids[2]}", headers=headers)
        assert get_res3.status_code == 404

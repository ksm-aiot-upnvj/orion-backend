import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.mark.asyncio
async def test_member_erp_access_lifecycle():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Login as Superadmin to perform administrative member operations
        admin_login = await ac.post(
            "/orion/api/v1/auth/login",
            json={"student_id": "2210511084", "password": "OrionAdmin#2026!"},
        )
        assert admin_login.status_code == 200
        admin_token = admin_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        # 2. Create a new member with ERP account enabled
        new_member_payload = {
            "student_id": "2410511888",
            "full_name": "Pengurus Test ERP",
            "program_of_study": "S1 Informatika",
            "semester": 4,
            "email": "pengurus_erp@upnvj.ac.id",
            "division": "PSDM",
            "role": "Staff",
            "intake_period": "2026",
            "status": "Aktif",
            "create_erp_account": True,
            "erp_password": "InitialPassword#2026!",
            "erp_role": "PENGURUS",
        }
        create_res = await ac.post("/orion/api/v1/members/", json=new_member_payload, headers=headers)
        assert create_res.status_code == 201
        created_data = create_res.json()
        assert created_data["has_erp_access"] is True
        assert created_data["student_id"] == "2410511888"

        # 3. Verify new pengurus can login with created credentials
        member_login = await ac.post(
            "/orion/api/v1/auth/login",
            json={"student_id": "2410511888", "password": "InitialPassword#2026!"},
        )
        assert member_login.status_code == 200
        assert "access_token" in member_login.json()
        assert member_login.json()["user"]["student_id"] == "2410511888"

        # 4. Revoke ERP access
        revoke_res = await ac.delete("/orion/api/v1/members/2410511888/access", headers=headers)
        assert revoke_res.status_code == 200
        assert revoke_res.json()["status"] == "success"

        # 5. Verify member login is now blocked because user is deactivated
        blocked_login = await ac.post(
            "/orion/api/v1/auth/login",
            json={"student_id": "2410511888", "password": "InitialPassword#2026!"},
        )
        assert blocked_login.status_code == 401

        # 6. Re-grant ERP access with new password
        grant_res = await ac.post(
            "/orion/api/v1/members/2410511888/access",
            json={"password": "ReactivatedPassword#2026!", "role": "PENGURUS"},
            headers=headers,
        )
        assert grant_res.status_code == 200

        # 7. Verify login works with new password
        re_login = await ac.post(
            "/orion/api/v1/auth/login",
            json={"student_id": "2410511888", "password": "ReactivatedPassword#2026!"},
        )
        assert re_login.status_code == 200

        # 8. Transition member to Alumni -> should automatically revoke ERP access
        alumni_update = await ac.put(
            "/orion/api/v1/members/2410511888",
            json={"status": "Alumni"},
            headers=headers,
        )
        assert alumni_update.status_code == 200
        assert alumni_update.json()["status"] == "Alumni"
        assert alumni_update.json()["has_erp_access"] is False

        # 9. Verify login blocked after becoming Alumni
        alumni_login = await ac.post(
            "/orion/api/v1/auth/login",
            json={"student_id": "2410511888", "password": "ReactivatedPassword#2026!"},
        )
        assert alumni_login.status_code == 401

        # 10. Clean up test member
        del_res = await ac.delete("/orion/api/v1/members/2410511888", headers=headers)
        assert del_res.status_code == 200

import csv
import uuid
from io import BytesIO, StringIO

from httpx import ASGITransport, AsyncClient
from openpyxl import load_workbook

from config.config import settings
from config.db import AsyncSessionLocal
from main import app
from services.registration_service import RegistrationService
from utils.auth_deps import get_current_user

API = "/orion/api/v1"


async def test_registration_exports_respect_selection_permissions_and_escape_cells():
    async with AsyncSessionLocal() as session:
        service = RegistrationService(session)
        registration = await service.create_registration({
            "student_id": "0410511887",
            "full_name": '=HYPERLINK("https://example.test","Nama")',
            "program_of_study": "S1 Informatika",
            "intake_period": "2026",
            "contact_info": "081234567890",
            "email": "test_selection_export@upnvj.ac.id",
            "motivation": "PRIVATE MOTIVATION",
        })
        identifier = str(registration["id"])

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                endpoint = f"{API}/registrations/export"
                payload = {"format": "csv", "registration_ids": [identifier]}
                assert (await client.post(endpoint, json=payload)).status_code == 401

                async def read_only_user():
                    return {"role": "Staff", "division": "Akademik Riset", "is_superadmin": False}

                app.dependency_overrides[get_current_user] = read_only_user
                try:
                    assert (await client.post(endpoint, json=payload)).status_code == 403
                finally:
                    app.dependency_overrides.pop(get_current_user)

                login = await client.post(
                    f"{API}/auth/login",
                    json={"student_id": settings.SUPERADMIN_NIM, "password": settings.SUPERADMIN_PW},
                )
                headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
                result = await client.post(endpoint, json=payload, headers=headers)
                assert result.status_code == 200, result.text
                assert result.headers["cache-control"] == "no-store"
                assert result.headers["content-disposition"].endswith('.csv"')
                rows = list(csv.reader(StringIO(result.content.decode("utf-8-sig"))))
                assert len(rows) == 2
                assert rows[1][0] == "'=HYPERLINK(\"https://example.test\",\"Nama\")"
                assert "PRIVATE MOTIVATION" not in result.text

                result = await client.post(endpoint, json={**payload, "format": "xlsx"}, headers=headers)
                assert result.status_code == 200
                workbook = load_workbook(BytesIO(result.content), read_only=True)
                try:
                    _, row = list(workbook.active.rows)
                    assert row[0].data_type == "s"
                    assert row[0].value.startswith("=")
                    assert row[1].value == "0410511887"
                    assert row[4].value == "081234567890"
                finally:
                    workbook.close()

                missing = {"format": "csv", "registration_ids": [identifier, str(uuid.uuid4())]}
                assert (await client.post(endpoint, json=missing, headers=headers)).status_code == 409
        finally:
            await service.delete_registration(identifier)

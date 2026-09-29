"""End-to-end file lifecycle: staged upload -> registration submit -> approve -> delete."""

import io

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import text

from config.config import settings
from config.db import AsyncSessionLocal, engine
from main import app
from services.storage_service import StorageService

API = "/orion/api/v1"
NIMS = ["2410511921", "2410511922"]


@pytest.fixture(autouse=True)
async def cleanup():
    yield
    async with AsyncSessionLocal() as session:
        await session.execute(text("DELETE FROM registrations WHERE student_id = ANY(:ids)"), {"ids": NIMS})
        await session.execute(text("DELETE FROM members WHERE student_id = ANY(:ids)"), {"ids": NIMS})
        await session.commit()
    await engine.dispose()


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color="green").save(buf, format="PNG")
    return buf.getvalue()


def _registration(nim: str, photo: str | None, cv: str | None) -> dict:
    return {
        "student_id": nim,
        "full_name": "Calon Anggota Consent Test",
        "program_of_study": "S1 Informatika",
        "email": f"consent_{nim}@upnvj.ac.id",
        "intake_period": "2026",
        "photo": photo,
        "cv_url": cv,
    }


@pytest.mark.asyncio
async def test_upload_submit_approve_delete_lifecycle():
    storage = StorageService()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        photo = (await ac.post(f"{API}/uploads/avatars", files={"file": ("p.png", _png(), "image/png")})).json()["path"]
        cv = (await ac.post(f"{API}/uploads/cvs", files={"file": ("c.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")})).json()["path"]
        assert photo.startswith("tmp/avatars/") and cv.startswith("tmp/cvs/")

        # A client-chosen permanent path (someone else's file) is refused
        res = await ac.post(f"{API}/registrations", json=_registration(NIMS[0], "avatars/0b1c2d3e-4f50-4a61-8b72-938495a6b7c8.webp", None))
        assert res.status_code == 400

        res = await ac.post(f"{API}/registrations", json=_registration(NIMS[0], photo, cv))
        assert res.status_code == 201, res.text
        reg = res.json()
        final_photo, final_cv = reg["photo"], reg["cv_url"]
        assert final_photo == photo.removeprefix("tmp/") and final_cv == cv.removeprefix("tmp/")
        assert (storage.base_dir / final_photo).is_file() and not (storage.base_dir / photo).exists()

        # Duplicate NIM fails after promotion -> files go back to staging so a retry needs no re-upload
        photo2 = (await ac.post(f"{API}/uploads/avatars", files={"file": ("p.png", _png(), "image/png")})).json()["path"]
        res = await ac.post(f"{API}/registrations", json=_registration(NIMS[0], photo2, None))
        assert res.status_code == 400
        assert (storage.base_dir / photo2).is_file()

        login = await ac.post(f"{API}/auth/login", json={"student_id": settings.SUPERADMIN_NIM, "password": settings.SUPERADMIN_PW})
        admin = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert (await ac.patch(f"{API}/registrations/{reg['id']}/approve", headers=admin)).status_code == 200

        # Deleting the registration keeps the photo (now the member's avatar) but removes the CV
        assert (await ac.delete(f"{API}/registrations/{reg['id']}", headers=admin)).status_code == 200
        assert (storage.base_dir / final_photo).is_file()
        assert not (storage.base_dir / final_cv).exists()

        # Replacing the member's avatar releases the old file
        new_avatar = (await ac.post(f"{API}/uploads/avatars", files={"file": ("p.png", _png(), "image/png")})).json()["path"]
        res = await ac.put(f"{API}/members/{NIMS[0]}", headers=admin, json={"avatar": new_avatar})
        assert res.status_code == 200, res.text
        assert res.json()["avatar"] == new_avatar.removeprefix("tmp/")
        assert not (storage.base_dir / final_photo).exists()
        storage.delete_upload(res.json()["avatar"])

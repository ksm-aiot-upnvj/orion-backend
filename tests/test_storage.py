import io
import os
import time

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from PIL import Image

from config.db import engine
from main import app
from services.storage_service import StorageService


@pytest.fixture(autouse=True)
async def cleanup():
    yield
    await engine.dispose()


def _staged_avatar(storage: StorageService) -> str:
    img_byte_arr = io.BytesIO()
    Image.new("RGB", (10, 10), color="blue").save(img_byte_arr, format="PNG")
    img_byte_arr.seek(0)
    return storage.process_and_save_avatar(img_byte_arr, "image/png")


def _staged_cv(storage: StorageService) -> str:
    return storage.process_and_save_cv(io.BytesIO(b"%PDF-1.4\n%test\n%%EOF"), "application/pdf")


@pytest.mark.asyncio
async def test_upload_avatar_exif_stripped_and_webp_converted():
    # Create test image with red color
    img_byte_arr = io.BytesIO()
    image = Image.new("RGB", (100, 100), color="red")
    image.save(img_byte_arr, format="JPEG")
    img_bytes = img_byte_arr.getvalue()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("test_avatar.jpg", img_bytes, "image/jpeg")}
        response = await ac.post("/orion/api/v1/uploads/avatar", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["filename"].endswith(".webp")
        # Uploads are staged until the owning form is saved
        assert data["path"] == f"tmp/avatars/{data['filename']}"
        assert data["url"].endswith(f"/uploads/tmp/avatars/{data['filename']}")

        filename = data["filename"]
        preview_res = await ac.get(f"/orion/api/v1/uploads/tmp/avatars/{filename}")
        assert preview_res.status_code == 200
        assert preview_res.headers["content-type"] == "image/webp"

        # Not served as a permanent file before promotion
        serve_res = await ac.get(f"/orion/api/v1/uploads/avatars/{filename}")
        assert serve_res.status_code == 404

        # After promotion it is served via both /uploads/avatars and direct /avatars route
        final_path = StorageService().promote_upload(data["path"], "avatars")
        assert final_path == f"avatars/{filename}"
        serve_res = await ac.get(f"/orion/api/v1/uploads/avatars/{filename}")
        assert serve_res.status_code == 200
        assert serve_res.headers["content-type"] == "image/webp"
        direct_res = await ac.get(f"/orion/api/v1/avatars/{filename}")
        assert direct_res.status_code == 200

        StorageService().delete_avatar(final_path)


@pytest.mark.asyncio
async def test_upload_avatar_invalid_file_type():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("test.txt", b"not an image", "text/plain")}
        response = await ac.post("/orion/api/v1/uploads/avatar", files=files)
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_cv_valid_pdf_and_serve():
    fake_pdf = b"%PDF-1.4\n%test pdf content\n%%EOF"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("cv_sample.pdf", fake_pdf, "application/pdf")}
        response = await ac.post("/orion/api/v1/uploads/cv", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["filename"].endswith(".pdf")
        assert data["path"] == f"tmp/cvs/{data['filename']}"

        filename = data["filename"]
        preview_res = await ac.get(f"/orion/api/v1/uploads/tmp/cvs/{filename}")
        assert preview_res.status_code == 200
        assert preview_res.headers["content-type"] == "application/pdf"

        final_path = StorageService().promote_upload(data["path"], "cvs")
        serve_res = await ac.get(f"/orion/api/v1/uploads/cvs/{filename}")
        assert serve_res.status_code == 200
        assert serve_res.headers["content-type"] == "application/pdf"
        assert "inline" in serve_res.headers.get("content-disposition", "")

        direct_res = await ac.get(f"/orion/api/v1/cvs/{filename}")
        assert direct_res.status_code == 200
        assert direct_res.headers["content-type"] == "application/pdf"

        StorageService().delete_cv(final_path)


@pytest.mark.asyncio
async def test_upload_cv_invalid_file_type():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("cv.docx", b"PK fake docx content", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        response = await ac.post("/orion/api/v1/uploads/cv", files=files)
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_staged_preview_rejects_traversal():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/orion/api/v1/uploads/tmp/avatars/..%2F..%2Fconfig.py")
        assert res.status_code == 404


def test_promote_moves_staged_file_into_permanent_storage(tmp_path):
    storage = StorageService(str(tmp_path))
    staged = _staged_avatar(storage)
    final = storage.promote_upload(staged, "avatars")

    assert final == staged.removeprefix("tmp/")
    assert (tmp_path / final).is_file()
    assert not (tmp_path / staged).exists()

    # A staged upload can be promoted only once
    with pytest.raises(HTTPException) as exc:
        storage.promote_upload(staged, "avatars")
    assert exc.value.status_code == 400


@pytest.mark.parametrize(
    "value",
    [
        "avatars/0b1c2d3e-4f50-4a61-8b72-938495a6b7c8.webp",  # someone else's permanent file
        "cvs/0b1c2d3e-4f50-4a61-8b72-938495a6b7c8.pdf",
        "tmp/avatars/../cvs/0b1c2d3e-4f50-4a61-8b72-938495a6b7c8.webp",
        "tmp/avatars/not-a-uuid.webp",
        "/etc/passwd",
    ],
)
def test_commit_upload_field_rejects_non_staged_paths(tmp_path, value):
    storage = StorageService(str(tmp_path))
    with pytest.raises(HTTPException) as exc:
        storage.commit_upload_field(value, "avatars")
    assert exc.value.status_code == 400


def test_commit_upload_field_rejects_wrong_kind(tmp_path):
    storage = StorageService(str(tmp_path))
    staged_cv = _staged_cv(storage)
    with pytest.raises(HTTPException):
        storage.commit_upload_field(staged_cv, "avatars")
    # The staged file is untouched and still promotable as a CV
    value, promoted = storage.commit_upload_field(staged_cv, "cvs")
    assert value == promoted == staged_cv.removeprefix("tmp/")


def test_commit_upload_field_keeps_current_and_external_values(tmp_path):
    storage = StorageService(str(tmp_path))
    current = "avatars/0b1c2d3e-4f50-4a61-8b72-938495a6b7c8.webp"
    assert storage.commit_upload_field(current, "avatars", keep_values={current}) == (current, None)
    assert storage.commit_upload_field("", "avatars") == (None, None)

    dicebear = "https://api.dicebear.com/7.x/bottts/svg?seed=x"
    assert storage.commit_upload_field(dicebear, "avatars", allow_external=True) == (dicebear, None)
    with pytest.raises(HTTPException):
        storage.commit_upload_field(dicebear, "avatars")


def test_unpromote_returns_file_to_staging(tmp_path):
    storage = StorageService(str(tmp_path))
    staged = _staged_cv(storage)
    final = storage.promote_upload(staged, "cvs")

    storage.unpromote_upload(final)
    assert (tmp_path / staged).is_file()
    assert not (tmp_path / final).exists()
    # Retrying the submit works without re-uploading
    assert storage.promote_upload(staged, "cvs") == final


def test_purge_stale_staged_only_removes_old_files(tmp_path):
    storage = StorageService(str(tmp_path))
    old_staged = _staged_avatar(storage)
    fresh_staged = _staged_cv(storage)
    permanent = storage.promote_upload(_staged_avatar(storage), "avatars")

    two_days_ago = time.time() - 2 * 86400
    os.utime(tmp_path / old_staged, (two_days_ago, two_days_ago))
    os.utime(tmp_path / permanent, (two_days_ago, two_days_ago))

    assert storage.purge_stale_staged(max_age_seconds=86400) == 1
    assert not (tmp_path / old_staged).exists()
    assert (tmp_path / fresh_staged).is_file()
    assert (tmp_path / permanent).is_file()

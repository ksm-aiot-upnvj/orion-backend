import io

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from config.db import engine
from main import app


@pytest.fixture(autouse=True)
async def cleanup():
    yield
    await engine.dispose()


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
        assert "filename" in data
        assert data["filename"].endswith(".webp")
        assert "path" in data
        assert data["path"].startswith("avatars/")

        # Test serving the file
        filename = data["filename"]
        serve_res = await ac.get(f"/orion/api/v1/uploads/avatars/{filename}")
        assert serve_res.status_code == 200
        assert serve_res.headers["content-type"] == "image/webp"


@pytest.mark.asyncio
async def test_upload_avatar_invalid_file_type():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("test.txt", b"not an image", "text/plain")}
        response = await ac.post("/orion/api/v1/uploads/avatar", files=files)
        assert response.status_code == 400

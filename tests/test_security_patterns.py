import io
import uuid
import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from config.db import AsyncSessionLocal, Base, engine
from main import app
from models import AuditLog, Member, Registration, User  # noqa: F401
from services.audit_log_service import AuditLogService, log_audit_event
from services.member_service import MemberService
from services.storage_service import StorageService, validate_image_magic_bytes
from utils.auth_deps import SystemRole, verify_resource_owner
from utils.rate_limiter import InMemoryRateLimiter, rate_limit


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    InMemoryRateLimiter.reset()
    yield
    InMemoryRateLimiter.reset()


@pytest.mark.asyncio
async def test_ensure_tables_and_rbac():
    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Login as SUPERADMIN
        login_res = await ac.post(
            "/orion/api/v1/auth/login",
            json={"student_id": "2210511084", "password": "OrionAdmin#2026!"},
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create a test member
        create_res = await ac.post(
            "/orion/api/v1/members/",
            headers=headers,
            json={
                "student_id": "2410511999",
                "full_name": "Test RBAC Member",
                "program_of_study": "S1 Informatika",
                "email": "test_rbac@upnvj.ac.id",
                "intake_period": "2026",
            },
        )
        assert create_res.status_code == 201

        # Anonymize member using SUPERADMIN
        anon_res = await ac.post(
            "/orion/api/v1/members/2410511999/anonymize",
            headers=headers,
        )
        assert anon_res.status_code == 200
        assert anon_res.json()["full_name"] == "[DELETED USER]"
        assert "anonymized.orion" in anon_res.json()["email"]

        # Hard delete
        del_res = await ac.delete("/orion/api/v1/members/2410511999", headers=headers)
        assert del_res.status_code == 200


@pytest.mark.asyncio
async def test_rbac_unauthenticated_request_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Attempt to delete member without token
        del_res = await ac.delete("/orion/api/v1/members/random_id")
        assert del_res.status_code == 401


# --- 2. Anti-BOLA / Anti-IDOR Tests ---
def test_verify_resource_owner():
    owner_uuid = uuid.uuid4()
    other_uuid = uuid.uuid4()

    owner_user = {"id": owner_uuid, "role": SystemRole.PENGURUS, "full_name": "Owner"}
    admin_user = {"id": other_uuid, "role": SystemRole.SUPERADMIN, "full_name": "Admin"}
    intruder_user = {"id": other_uuid, "role": SystemRole.PENGURUS, "full_name": "Intruder"}

    # 1. Owner can access their own resource
    assert verify_resource_owner(owner_user, owner_uuid) is True

    # 2. Admin can access other's resource
    assert verify_resource_owner(admin_user, owner_uuid) is True

    # 3. Non-owner non-admin is blocked with 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        verify_resource_owner(intruder_user, owner_uuid)
    assert exc_info.value.status_code == 403
    assert "Anti-IDOR" in exc_info.value.detail


# --- 3. Magic Bytes Image Validation Tests ---
def test_magic_bytes_validation():
    # Valid JPEG magic bytes
    valid_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01"
    assert validate_image_magic_bytes(valid_jpeg) == "image/jpeg"

    # Valid PNG magic bytes
    valid_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    assert validate_image_magic_bytes(valid_png) == "image/png"

    # Valid WebP magic bytes
    valid_webp = b"RIFF\x00\x00\x00\x00WEBPVP8 "
    assert validate_image_magic_bytes(valid_webp) == "image/webp"

    # Malicious fake script disguised as image
    fake_script = b"<?php echo 'malicious code'; ?>"
    with pytest.raises(HTTPException) as exc_info:
        validate_image_magic_bytes(fake_script)
    assert exc_info.value.status_code == 400
    assert "Magic Bytes" in exc_info.value.detail


# --- 4. Rate Limiter Tests ---
def test_rate_limiter_logic():
    key = "test_client_ip"
    max_requests = 3
    window = 10

    # 3 requests allowed
    assert InMemoryRateLimiter.is_allowed(key, max_requests, window)[0] is True
    assert InMemoryRateLimiter.is_allowed(key, max_requests, window)[0] is True
    assert InMemoryRateLimiter.is_allowed(key, max_requests, window)[0] is True

    # 4th request blocked with retry_after > 0
    allowed, retry_after = InMemoryRateLimiter.is_allowed(key, max_requests, window)
    assert allowed is False
    assert retry_after > 0


# --- 5. Audit Log Service Tests ---
@pytest.mark.asyncio
async def test_audit_log_service():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        service = AuditLogService(session)
        test_actor_id = uuid.uuid4()

        # Insert audit log
        log_entry = await service.log_event(
            action="TEST_SECURITY_AUDIT",
            resource_type="SECURITY_TEST",
            actor_id=test_actor_id,
            actor_name="Automated Auditor",
            actor_role="TESTER",
            resource_id="TEST-001",
            details={"test_key": "test_value"},
        )
        assert log_entry is not None
        assert log_entry["action"] == "TEST_SECURITY_AUDIT"
        assert log_entry["resource_type"] == "SECURITY_TEST"

        # Query logs
        logs = await service.get_logs(resource_type="SECURITY_TEST", limit=5)
        assert len(logs) >= 1
        assert logs[0]["action"] == "TEST_SECURITY_AUDIT"


# --- 6. Security Headers Check ---
@pytest.mark.asyncio
async def test_security_headers_present():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/health")
        assert res.status_code == 200
        assert res.headers.get("X-Content-Type-Options") == "nosniff"
        assert res.headers.get("X-Frame-Options") == "DENY"
        assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "max-age=31536000" in res.headers.get("Strict-Transport-Security", "")

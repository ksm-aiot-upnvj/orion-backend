import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import services.auth_service as auth_service_module
from models.enums import MemberStatus
from schemas.auth import LoginRequest
from services.auth_service import AuthService
from services.member_service import MemberService
from utils import auth_deps
from utils.security import create_access_token, create_refresh_token, decode_access_token, decode_refresh_token


@pytest.mark.asyncio
async def test_refresh_token_from_previous_version_is_rejected():
    user_id = uuid.uuid4()
    service = AuthService(object())
    service.get_user_by_id = AsyncMock(return_value={"id": user_id, "is_active": True, "token_version": 2})
    token = create_refresh_token({"sub": str(user_id), "token_version": 1})

    with pytest.raises(HTTPException) as error:
        await service.refresh_tokens(token)

    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_access_token_from_previous_version_is_rejected(monkeypatch):
    user_id = uuid.uuid4()
    service = SimpleNamespace(
        get_user_by_id=AsyncMock(return_value={"id": user_id, "token_version": 2})
    )
    monkeypatch.setattr(auth_deps, "AuthService", lambda _db: service)
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=create_access_token({"sub": str(user_id), "token_version": 1}),
    )

    with pytest.raises(HTTPException) as error:
        await auth_deps.get_current_user(credentials=credentials, db=object())

    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_logout_session_revocation_increments_token_version():
    user_id = uuid.uuid4()
    session = SimpleNamespace(execute=AsyncMock(), commit=AsyncMock())

    await AuthService(session).revoke_user_sessions(user_id)

    statement = str(session.execute.await_args.args[0])
    assert "token_version = token_version + 1" in statement
    assert session.execute.await_args.args[1] == {"user_id": user_id}
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("new_status", [MemberStatus.TIDAK_AKTIF.value, MemberStatus.ALUMNI.value])
async def test_membership_deactivation_increments_token_version(new_status):
    member_id = uuid.uuid4()
    session = SimpleNamespace(execute=AsyncMock())
    service = MemberService(session)
    service.get_member_by_identifier = AsyncMock(return_value={"user_is_superadmin": False, "user_role": "PENGURUS"})

    await service.sync_membership_access(member_id, "2410511001", new_status, actor=None)

    statement = str(session.execute.await_args_list[0].args[0])
    assert "token_version = token_version + 1" in statement
    if new_status == MemberStatus.ALUMNI.value:
        assert "NOT (is_superadmin OR UPPER(role) = 'SUPERADMIN')" in statement
        assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_password_change_increments_token_version(monkeypatch):
    user_id = uuid.uuid4()
    session = SimpleNamespace(execute=AsyncMock(), commit=AsyncMock())
    service = AuthService(session)
    service.get_user_by_id = AsyncMock(return_value={
        "id": user_id,
        "hashed_password": "old-hash",
        "full_name": "Test User",
        "role": "PENGURUS",
    })
    monkeypatch.setattr(auth_service_module, "verify_password", lambda *_args: True)
    monkeypatch.setattr(auth_service_module, "hash_password", lambda _password: "new-hash")
    monkeypatch.setattr(auth_service_module, "log_audit_event", AsyncMock())

    await service.change_password(user_id, SimpleNamespace(current_password="old", new_password="new"))

    statement = str(session.execute.await_args.args[0])
    assert "token_version = token_version + 1" in statement
    assert session.commit.await_count == 1


@pytest.mark.asyncio
async def test_login_and_refresh_tokens_carry_current_version(monkeypatch):
    user_id = uuid.uuid4()
    user = {
        "id": user_id,
        "member_id": None,
        "student_id": "2410511001",
        "full_name": "Test User",
        "email": "test@example.com",
        "hashed_password": "hashed",
        "role": "PENGURUS",
        "division": None,
        "avatar": None,
        "is_superadmin": False,
        "is_active": True,
        "token_version": 4,
        "created_at": datetime.now(UTC),
    }
    session = SimpleNamespace()
    service = AuthService(session)
    service.get_user_by_identifier = AsyncMock(return_value=user)
    service.get_user_by_id = AsyncMock(return_value=user)
    monkeypatch.setattr(auth_service_module, "verify_password", lambda *_args: True)
    monkeypatch.setattr(auth_service_module, "log_audit_event", AsyncMock())

    login = await service.authenticate_user(LoginRequest(student_id=user["student_id"], password="pass"))
    refreshed = await service.refresh_tokens(login.refresh_token)

    assert decode_access_token(login.access_token)["token_version"] == 4
    assert decode_refresh_token(login.refresh_token)["token_version"] == 4
    assert decode_access_token(refreshed["access_token"])["token_version"] == 4
    assert decode_refresh_token(refreshed["refresh_token"])["token_version"] == 4


@pytest.mark.asyncio
async def test_failed_login_does_not_persist_raw_identifier(monkeypatch):
    audit_events = []

    async def record_audit_event(**kwargs):
        audit_events.append(kwargs)

    monkeypatch.setattr(AuthService, "get_user_by_identifier", AsyncMock(return_value=None))
    monkeypatch.setattr(auth_service_module, "log_audit_event", record_audit_event)
    service = AuthService(object())

    with pytest.raises(HTTPException) as error:
        await service.authenticate_user(LoginRequest(student_id="do-not-log-this-secret", password="wrong"))

    assert error.value.status_code == 401
    event = audit_events[0]
    assert event["details"]["identifier_type"] == "other"
    assert "do-not-log-this-secret" not in event["details"].values()
    assert "do-not-log-this-secret" not in str(event)

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.auth import ChangePasswordRequest, LoginRequest, LoginResponse, ProfileUpdate, UserOut
from services.audit_log_service import log_audit_event
from utils.sanitizer import sanitize_text
from utils.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_identifier(self, identifier: str) -> dict | None:
        """Fetch user by NIM (student_id) or email using raw parameterized SQL with LEFT JOIN members."""
        stmt = text(
            """
            SELECT u.id, u.student_id, u.full_name, u.email, u.hashed_password,
                   CASE WHEN u.is_superadmin = true THEN 'SUPERADMIN' ELSE COALESCE(m.role::text, u.role) END AS role,
                   COALESCE(m.division::text, u.division::text) AS division,
                   COALESCE(u.member_id, m.id) AS member_id,
                   COALESCE(u.avatar, m.avatar) AS avatar, u.is_superadmin, u.is_active, u.created_at
            FROM users u
            LEFT JOIN members m ON u.student_id = m.student_id
            WHERE (u.student_id = :identifier OR u.email = :identifier) AND u.is_active = true
            """
        )
        result = await self.session.execute(stmt, {"identifier": identifier})
        return result.mappings().first()

    async def get_user_by_id(self, user_id: uuid.UUID) -> dict | None:
        """Fetch user by UUID using raw parameterized SQL with LEFT JOIN members."""
        stmt = text(
            """
            SELECT u.id, u.student_id, u.full_name, u.email, u.hashed_password,
                   CASE WHEN u.is_superadmin = true THEN 'SUPERADMIN' ELSE COALESCE(m.role::text, u.role) END AS role,
                   COALESCE(m.division::text, u.division::text) AS division,
                   COALESCE(u.member_id, m.id) AS member_id,
                   COALESCE(u.avatar, m.avatar) AS avatar, u.is_superadmin, u.is_active, u.created_at
            FROM users u
            LEFT JOIN members m ON u.student_id = m.student_id
            WHERE u.id = :user_id AND u.is_active = true
            """
        )
        result = await self.session.execute(stmt, {"user_id": user_id})
        return result.mappings().first()

    async def authenticate_user(
        self,
        req: LoginRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> LoginResponse:
        """Authenticate user credentials using raw SQL and record audit log with superadmin & readable resource tracking."""
        identifier = req.student_id.strip()
        user = await self.get_user_by_identifier(identifier)

        if not user or not verify_password(req.password, user["hashed_password"]):
            # Record failed login attempt in audit log
            await log_audit_event(
                session=self.session,
                action="AUTH_LOGIN_FAILED",
                resource_type="USER",
                resource_id=f"Akun: {identifier}",
                actor_id=user["id"] if user else None,
                actor_name=user["full_name"] if user else identifier,
                actor_role=user["role"] if user else "UNKNOWN",
                ip_address=ip_address,
                user_agent=user_agent,
                status="FAILED",
                details={"identifier": identifier, "is_superadmin": bool(user.get("is_superadmin", False)) if user else False},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="NIM / Email atau Password salah. Silakan coba lagi.",
            )

        is_sa = bool(user.get("is_superadmin", False))
        effective_role = "SUPERADMIN" if is_sa else (user.get("role") or "USER")

        access_token = create_access_token(
            data={
                "sub": str(user["id"]),
                "student_id": user["student_id"],
                "role": effective_role,
                "division": user.get("division"),
                "is_superadmin": is_sa,
                "name": user["full_name"],
            }
        )

        refresh_token = create_refresh_token(
            data={
                "sub": str(user["id"]),
                "student_id": user["student_id"],
            }
        )

        # Human-readable Resource info (e.g. "Akun: 2310511001 (Dzulfikri Adjmal)") instead of cold UUID
        readable_resource = f"Akun: {user['student_id']} ({user['full_name']})"

        # Record successful login in audit log with is_superadmin tracking
        await log_audit_event(
            session=self.session,
            action="AUTH_LOGIN_SUCCESS",
            resource_type="USER",
            resource_id=readable_resource,
            actor_id=user["id"],
            actor_name=user["full_name"],
            actor_role=effective_role,
            ip_address=ip_address,
            user_agent=user_agent,
            status="SUCCESS",
            details={
                "is_superadmin": is_sa,
                "student_id": user["student_id"],
                "role": effective_role,
                "division": user.get("division"),
            },
        )

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user=UserOut.model_validate(user),
        )

    async def refresh_tokens(self, refresh_token_str: str) -> dict:
        """Validate 7-day refresh token and issue a fresh 30-minute access token."""
        payload = decode_refresh_token(refresh_token_str)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesi refresh token telah kedaluwarsa atau tidak valid. Silakan login kembali.",
            )

        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Payload refresh token tidak valid.",
            )

        try:
            user_uuid = uuid.UUID(user_id_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Format UUID user tidak valid.",
            )

        user = await self.get_user_by_id(user_uuid)
        if not user or not user.get("is_active"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Akun pengguna tidak aktif atau tidak ditemukan.",
            )

        is_sa = bool(user.get("is_superadmin", False))
        effective_role = "SUPERADMIN" if is_sa else (user.get("role") or "USER")

        new_access_token = create_access_token(
            data={
                "sub": str(user["id"]),
                "student_id": user["student_id"],
                "role": effective_role,
                "division": user.get("division"),
                "is_superadmin": is_sa,
                "name": user["full_name"],
            }
        )

        # Issue fresh refresh token for continuous active sessions
        new_refresh_token = create_refresh_token(
            data={
                "sub": str(user["id"]),
                "student_id": user["student_id"],
            }
        )

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "user": UserOut.model_validate(user),
        }

    async def update_profile(self, user_id: uuid.UUID, data: ProfileUpdate) -> dict:
        """Update current logged-in user profile with sanitization and audit log."""
        updates = []
        params: dict[str, Any] = {"user_id": user_id}
        if data.full_name is not None:
            updates.append("full_name = :full_name")
            params["full_name"] = sanitize_text(data.full_name)
        if data.email is not None:
            updates.append("email = :email")
            params["email"] = sanitize_text(data.email)
        if data.avatar is not None:
            updates.append("avatar = :avatar")
            params["avatar"] = data.avatar

        if not updates:
            user = await self.get_user_by_id(user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User tidak ditemukan")
            return user

        stmt = text(
            f"""
            UPDATE users
            SET {', '.join(updates)}
            WHERE id = :user_id
            """
        )
        await self.session.execute(stmt, params)
        await self.session.commit()
        updated_user = await self.get_user_by_id(user_id)
        if not updated_user:
            raise HTTPException(status_code=404, detail="User tidak ditemukan")

        await log_audit_event(
            session=self.session,
            action="PROFILE_UPDATED",
            resource_type="USER",
            resource_id=str(user_id),
            actor_id=user_id,
            actor_name=updated_user["full_name"],
            actor_role=updated_user["role"],
        )

        return updated_user

    async def change_password(self, user_id: uuid.UUID, req: ChangePasswordRequest) -> bool:
        """Change current user password after verifying current password."""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User tidak ditemukan")

        if not verify_password(req.current_password, user["hashed_password"]):
            await log_audit_event(
                session=self.session,
                action="PASSWORD_CHANGE_FAILED",
                resource_type="USER",
                resource_id=str(user_id),
                actor_id=user_id,
                actor_name=user["full_name"],
                actor_role=user["role"],
                status="FAILED",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password saat ini (lama) tidak sesuai",
            )

        new_hashed = hash_password(req.new_password)
        stmt = text(
            """
            UPDATE users
            SET hashed_password = :hashed_password
            WHERE id = :user_id
            """
        )
        await self.session.execute(stmt, {"hashed_password": new_hashed, "user_id": user_id})
        await self.session.commit()

        await log_audit_event(
            session=self.session,
            action="PASSWORD_CHANGED_SUCCESS",
            resource_type="USER",
            resource_id=str(user_id),
            actor_id=user_id,
            actor_name=user["full_name"],
            actor_role=user["role"],
            status="SUCCESS",
        )
        return True

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.auth import ChangePasswordRequest, LoginRequest, LoginResponse, ProfileUpdate, UserOut
from services.audit_log_service import log_audit_event
from utils.sanitizer import sanitize_text
from utils.security import create_access_token, create_refresh_token, hash_password, verify_password


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_identifier(self, identifier: str) -> dict | None:
        """Fetch user by NIM (student_id) or email using raw parameterized SQL."""
        stmt = text(
            """
            SELECT id, student_id, full_name, email, hashed_password, role, division, avatar, is_active, created_at
            FROM users
            WHERE (student_id = :identifier OR email = :identifier) AND is_active = true
            """
        )
        result = await self.session.execute(stmt, {"identifier": identifier})
        return result.mappings().first()

    async def get_user_by_id(self, user_id: uuid.UUID) -> dict | None:
        """Fetch user by UUID using raw parameterized SQL."""
        stmt = text(
            """
            SELECT id, student_id, full_name, email, hashed_password, role, division, avatar, is_active, created_at
            FROM users
            WHERE id = :user_id AND is_active = true
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
        """Authenticate user credentials using raw SQL and record audit log."""
        identifier = req.student_id.strip()
        user = await self.get_user_by_identifier(identifier)

        if not user or not verify_password(req.password, user["hashed_password"]):
            # Record failed login attempt in audit log
            await log_audit_event(
                session=self.session,
                action="AUTH_LOGIN_FAILED",
                resource_type="USER",
                actor_id=user["id"] if user else None,
                actor_name=user["full_name"] if user else identifier,
                actor_role=user["role"] if user else "UNKNOWN",
                ip_address=ip_address,
                user_agent=user_agent,
                status="FAILED",
                details={"identifier": identifier},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="NIM / Email atau Password salah. Silakan coba lagi.",
            )

        token = create_access_token(
            data={
                "sub": str(user["id"]),
                "student_id": user["student_id"],
                "role": user["role"],
                "name": user["full_name"],
            }
        )

        # Record successful login in audit log
        await log_audit_event(
            session=self.session,
            action="AUTH_LOGIN_SUCCESS",
            resource_type="USER",
            resource_id=str(user["id"]),
            actor_id=user["id"],
            actor_name=user["full_name"],
            actor_role=user["role"],
            ip_address=ip_address,
            user_agent=user_agent,
            status="SUCCESS",
        )

        return LoginResponse(
            access_token=token,
            token_type="bearer",
            user=UserOut.model_validate(user),
        )

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
            RETURNING id, student_id, full_name, email, role, division, avatar, is_active, created_at
            """
        )
        result = await self.session.execute(stmt, params)
        await self.session.commit()
        updated_user = result.mappings().first()
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

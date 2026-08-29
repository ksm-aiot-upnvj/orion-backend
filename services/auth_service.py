import uuid

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.auth import LoginRequest, LoginResponse, UserOut
from utils.security import create_access_token, verify_password


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

    async def authenticate_user(self, req: LoginRequest) -> LoginResponse:
        """Authenticate user credentials using raw SQL."""
        identifier = req.student_id.strip()
        user = await self.get_user_by_identifier(identifier)

        if not user or not verify_password(req.password, user["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="NIM / Email atau Password salah. Silakan coba lagi."
            )

        token = create_access_token(
            data={
                "sub": str(user["id"]),
                "student_id": user["student_id"],
                "role": user["role"],
                "name": user["full_name"]
            }
        )

        return LoginResponse(
            access_token=token,
            token_type="bearer",
            user=UserOut.model_validate(user)
        )

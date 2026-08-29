import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from config.db import get_db
from services.auth_service import AuthService
from utils.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/orion/api/v1/auth/login", auto_error=False)

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> dict:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autentikasi diperlukan. Silakan login sebagai Pengurus KSM.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token tidak valid atau telah kedaluwarsa.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Data sesi tidak lengkap.",
        )

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Format UUID user tidak valid.",
        )

    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(user_uuid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Pengguna tidak ditemukan atau dinonaktifkan.",
        )
    return user

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from config.db import get_db
from schemas.auth import LoginRequest, LoginResponse, UserOut
from services.auth_service import AuthService
from utils.auth_deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate pengurus KSM using raw SQL."""
    service = AuthService(db)
    return await service.authenticate_user(req)

@router.get("/me", response_model=UserOut)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get currently logged-in pengurus profile."""
    return UserOut.model_validate(current_user)

@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Logout current session."""
    return {"message": "Sesi berhasil ditutup. Sampai jumpa kembali!", "user": current_user["full_name"]}

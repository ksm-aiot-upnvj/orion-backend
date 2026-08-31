from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from config.db import get_db
from schemas.auth import ChangePasswordRequest, LoginRequest, LoginResponse, ProfileUpdate, UserOut
from services.audit_log_service import log_audit_event
from services.auth_service import AuthService
from utils.auth_deps import get_current_user
from utils.rate_limiter import rate_limit

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=LoginResponse,
    dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60, scope="login"))],
)
async def login(
    req: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate pengurus KSM with Rate Limiting (5 attempts / min) and audit logging.
    """
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "127.0.0.1")
    user_agent = request.headers.get("User-Agent", "Unknown")

    service = AuthService(db)
    return await service.authenticate_user(req, ip_address=client_ip, user_agent=user_agent)


@router.get("/me", response_model=UserOut)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get currently logged-in pengurus profile."""
    return UserOut.model_validate(current_user)


@router.put("/me", response_model=UserOut)
async def update_my_profile(
    payload: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update logged-in user profile (full name, email, avatar)."""
    service = AuthService(db)
    updated = await service.update_profile(current_user["id"], payload)
    return UserOut.model_validate(updated)


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Change logged-in user password."""
    service = AuthService(db)
    await service.change_password(current_user["id"], payload)
    return {"status": "success", "message": "Password berhasil diperbarui secara aman."}


@router.post("/logout")
async def logout(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Logout current session and record audit trail."""
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "127.0.0.1")
    await log_audit_event(
        session=db,
        action="AUTH_LOGOUT",
        resource_type="USER",
        resource_id=str(current_user["id"]),
        actor_id=current_user["id"],
        actor_name=current_user["full_name"],
        actor_role=current_user["role"],
        ip_address=client_ip,
    )
    return {"message": "Sesi berhasil ditutup. Sampai jumpa kembali!", "user": current_user["full_name"]}

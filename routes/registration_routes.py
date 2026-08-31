from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from config.db import get_db
from models.enums import MemberRole
from schemas.registration import RegistrationCreate, RegistrationResponse, RegistrationReview
from services.registration_service import RegistrationService
from utils.auth_deps import get_current_user, require_roles
from utils.rate_limiter import rate_limit

router = APIRouter(prefix="/registrations", tags=["Registrations (Recruitment)"])


@router.post(
    "/",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, scope="registration_submit"))],
)
async def submit_registration(
    payload: RegistrationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Public endpoint: Submit candidate registration with explicit UU PDP consent and rate limiting.
    """
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "127.0.0.1")
    user_agent = request.headers.get("User-Agent", "Unknown")

    service = RegistrationService(db)
    reg = await service.create_registration(payload.model_dump(), ip_address=client_ip, user_agent=user_agent)
    return RegistrationResponse.model_validate(reg)


@router.get("/", response_model=list[RegistrationResponse])
async def list_registrations(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List registrations using raw SQL."""
    service = RegistrationService(db)
    regs = await service.get_all_registrations(status_filter=status)
    return [RegistrationResponse.model_validate(r) for r in regs]


@router.get("/{identifier}", response_model=RegistrationResponse)
async def get_registration(
    identifier: str,
    db: AsyncSession = Depends(get_db),
):
    """Get single registration by UUID or student_id using raw SQL."""
    service = RegistrationService(db)
    reg = await service.get_registration_by_identifier(identifier)
    if not reg:
        raise HTTPException(status_code=404, detail="Data pendaftaran tidak ditemukan")
    return RegistrationResponse.model_validate(reg)


@router.patch("/{identifier}/approve", response_model=RegistrationResponse)
async def approve_registration(
    identifier: str,
    payload: RegistrationReview | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_roles("SUPERADMIN", "ADMIN_BPH", "PENGURUS")),
):
    """
    Admin endpoint: Approve candidate and generate official Member ID using raw SQL.
    Enforced RBAC: SUPERADMIN, ADMIN_BPH, or PENGURUS.
    """
    service = RegistrationService(db)
    reg = await service.approve_registration(
        identifier=identifier,
        reviewer_name=current_user["full_name"],
        reviewer_role=current_user["role"],
        reviewer_id=current_user["id"],
        division=payload.division if payload else None,
        role=payload.role if payload else MemberRole.ANGGOTA,
    )
    return RegistrationResponse.model_validate(reg)


@router.patch("/{identifier}/reject", response_model=RegistrationResponse)
async def reject_registration(
    identifier: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_roles("SUPERADMIN", "ADMIN_BPH", "PENGURUS")),
):
    """
    Admin endpoint: Reject candidate application using raw SQL.
    Enforced RBAC: SUPERADMIN, ADMIN_BPH, or PENGURUS.
    """
    service = RegistrationService(db)
    reg = await service.reject_registration(
        identifier=identifier,
        reviewer_name=current_user["full_name"],
        reviewer_role=current_user["role"],
        reviewer_id=current_user["id"],
    )
    return RegistrationResponse.model_validate(reg)


@router.delete("/{identifier}")
async def delete_registration(
    identifier: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_roles("SUPERADMIN", "ADMIN_BPH")),
):
    """
    Admin endpoint: Hard delete registration and unlink physical photo (Right to Erasure).
    Enforced RBAC: SUPERADMIN or ADMIN_BPH.
    """
    service = RegistrationService(db)
    success = await service.delete_registration(identifier, actor=current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Data pendaftaran tidak ditemukan.")
    return {"status": "success", "message": "Data pendaftaran dan file foto berhasil dihapus permanen (Right to Erasure)."}

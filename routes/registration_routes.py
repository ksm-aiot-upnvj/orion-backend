from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from config.db import get_db
from schemas.registration import RegistrationCreate, RegistrationResponse
from services.registration_service import RegistrationService
from utils.auth_deps import get_current_user

router = APIRouter(prefix="/registrations", tags=["Registrations (Recruitment)"])

@router.post("/", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED)
async def submit_registration(payload: RegistrationCreate, db: AsyncSession = Depends(get_db)):
    """Public endpoint: Submit candidate registration using raw SQL."""
    service = RegistrationService(db)
    reg = await service.create_registration(payload.model_dump())
    return RegistrationResponse.model_validate(reg)

@router.get("/", response_model=list[RegistrationResponse])
async def list_registrations(
    status: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    """List registrations using raw SQL."""
    service = RegistrationService(db)
    regs = await service.get_all_registrations(status_filter=status)
    return [RegistrationResponse.model_validate(r) for r in regs]

@router.get("/{identifier}", response_model=RegistrationResponse)
async def get_registration(
    identifier: str,
    db: AsyncSession = Depends(get_db)
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
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Admin endpoint: Approve candidate and generate official Member ID using raw SQL."""
    service = RegistrationService(db)
    reg = await service.approve_registration(
        identifier=identifier,
        reviewer_name=current_user["full_name"],
        reviewer_role=current_user["role"]
    )
    return RegistrationResponse.model_validate(reg)

@router.patch("/{identifier}/reject", response_model=RegistrationResponse)
async def reject_registration(
    identifier: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Admin endpoint: Reject candidate application using raw SQL."""
    service = RegistrationService(db)
    reg = await service.reject_registration(
        identifier=identifier,
        reviewer_name=current_user["full_name"],
        reviewer_role=current_user["role"]
    )
    return RegistrationResponse.model_validate(reg)

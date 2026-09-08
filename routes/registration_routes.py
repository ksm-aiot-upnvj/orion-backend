import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config.db import get_db
from models.enums import MemberRole
from schemas.registration import (
    BulkDeleteRegistrationsRequest,
    BulkDeleteRegistrationsResponse,
    IntakeStatusResponse,
    IntakeStatusUpdate,
    RegistrationCreate,
    RegistrationResponse,
    RegistrationReview,
)
from services.registration_service import RegistrationService
from utils.auth_deps import can_manage_selection, require_pengurus
from utils.rate_limiter import rate_limit
from utils.uuid_utils import generate_uuid7

router = APIRouter(prefix="/registrations", tags=["Registrations (Recruitment)"])


@router.get("/intake-status", response_model=IntakeStatusResponse)
async def get_intake_status(db: AsyncSession = Depends(get_db)):
    """
    Public endpoint: Get active recruitment intake configuration from database.
    Used by registration portal and admin selection dashboard.
    """
    stmt = text("SELECT id, key, value, updated_at, updated_by FROM system_settings WHERE key = 'intake_config'")
    res = await db.execute(stmt)
    row = res.mappings().first()
    if not row:
        return IntakeStatusResponse(
            status="OPEN",
            batch_name="Penerimaan Anggota Baru Periode 2026",
            deadline="2026-08-31",
            quota=100,
        )
    try:
        val = json.loads(row["value"])
    except Exception:
        val = {}
    return IntakeStatusResponse(
        status=val.get("status", "OPEN"),
        batch_name=val.get("batch_name", "Penerimaan Anggota Baru Periode 2026"),
        deadline=val.get("deadline", "2026-08-31"),
        quota=int(val.get("quota", 100)),
        updated_at=row["updated_at"],
        updated_by=row["updated_by"],
    )


@router.put("/intake-status", response_model=IntakeStatusResponse)
async def update_intake_status(
    payload: IntakeStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(can_manage_selection),
):
    """
    Admin endpoint: Update recruitment intake status, batch name, deadline date, and quota in PostgreSQL.
    Enforced RBAC: Superadmin, Ketua, Wakil Ketua, or PSDM Division.
    """
    val_str = json.dumps({
        "status": payload.status.upper(),
        "batch_name": payload.batch_name.strip(),
        "deadline": payload.deadline.strip(),
        "quota": payload.quota,
    }, ensure_ascii=False)

    stmt = text(
        """
        INSERT INTO system_settings (id, key, value, description, updated_at, updated_by)
        VALUES (:id, 'intake_config', :value, 'Pengaturan Periode Penerimaan Calon Anggota KSM AIoT', NOW(), :updated_by)
        ON CONFLICT (key) DO UPDATE SET
            value = EXCLUDED.value,
            updated_at = NOW(),
            updated_by = EXCLUDED.updated_by
        RETURNING id, key, value, updated_at, updated_by;
        """
    )
    res = await db.execute(stmt, {
        "id": generate_uuid7(),
        "value": val_str,
        "updated_by": current_user["id"],
    })
    await db.commit()
    row = res.mappings().first()
    val = json.loads(row["value"])
    return IntakeStatusResponse(
        status=val.get("status", "OPEN"),
        batch_name=val.get("batch_name", "Penerimaan Anggota Baru Periode 2026"),
        deadline=val.get("deadline", "2026-08-31"),
        quota=int(val.get("quota", 100)),
        updated_at=row["updated_at"],
        updated_by=row["updated_by"],
    )


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
    Public endpoint: Submit candidate registration with server-side intake status & deadline enforcement.
    """
    # 1. Enforce intake status & deadline from database
    stmt = text("SELECT value FROM system_settings WHERE key = 'intake_config'")
    res = await db.execute(stmt)
    row = res.mappings().first()
    if row:
        try:
            cfg = json.loads(row["value"])
            if cfg.get("status") == "CLOSED":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Pendaftaran calon anggota KSM AIoT periode ini telah ditutup oleh panitia.",
                )
            deadline_str = cfg.get("deadline")
            if deadline_str:
                deadline_date = datetime.strptime(deadline_str[:10], "%Y-%m-%d").date()
                if datetime.now(UTC).date() > deadline_date:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Batas waktu pendaftaran (deadline) untuk periode ini telah berakhir.",
                    )
        except HTTPException:
            raise
        except Exception:
            pass

    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "127.0.0.1")
    user_agent = request.headers.get("User-Agent", "Unknown")

    service = RegistrationService(db)
    reg = await service.create_registration(payload.model_dump(), ip_address=client_ip, user_agent=user_agent)
    return RegistrationResponse.model_validate(reg)


@router.get("/", response_model=list[RegistrationResponse])
async def list_registrations(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_pengurus),
):
    """List registrations. Enforced RBAC: Pengurus / BPH / Superadmin only (Anggota Umum is denied)."""
    service = RegistrationService(db)
    regs = await service.get_all_registrations(status_filter=status)
    return [RegistrationResponse.model_validate(r) for r in regs]


@router.get("/{identifier}", response_model=RegistrationResponse)
async def get_registration(
    identifier: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_pengurus),
):
    """Get single registration by UUID or student_id. Enforced RBAC: Pengurus only."""
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
    current_user: dict = Depends(can_manage_selection),
):
    """
    Admin endpoint: Approve candidate and generate official Member ID using raw SQL.
    Enforced RBAC: Superadmin, Ketua, Wakil Ketua, or PSDM.
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
    current_user: dict = Depends(can_manage_selection),
):
    """
    Admin endpoint: Reject candidate application using raw SQL.
    Enforced RBAC: Superadmin, Ketua, Wakil Ketua, or PSDM.
    """
    service = RegistrationService(db)
    reg = await service.reject_registration(
        identifier=identifier,
        reviewer_name=current_user["full_name"],
        reviewer_role=current_user["role"],
        reviewer_id=current_user["id"],
    )
    return RegistrationResponse.model_validate(reg)


@router.post("/bulk-delete", response_model=BulkDeleteRegistrationsResponse)
async def bulk_delete_registrations(
    payload: BulkDeleteRegistrationsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(can_manage_selection),
):
    """
    Admin endpoint: Bulk hard delete registrations and unlink physical photos (Right to Erasure).
    Enforced RBAC: Superadmin, Ketua, Wakil Ketua, or PSDM.
    """
    service = RegistrationService(db)
    deleted_count = await service.bulk_delete_registrations(payload.registration_ids, actor=current_user)
    return BulkDeleteRegistrationsResponse(
        status="success",
        deleted_count=deleted_count,
        message=f"{deleted_count} data pendaftaran berhasil dihapus permanen (Right to Erasure).",
    )


@router.delete("/{identifier}")
async def delete_registration(
    identifier: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(can_manage_selection),
):
    """
    Admin endpoint: Hard delete registration and unlink physical photo (Right to Erasure).
    Enforced RBAC: Superadmin, Ketua, Wakil Ketua, or PSDM.
    """
    service = RegistrationService(db)
    success = await service.delete_registration(identifier, actor=current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Data pendaftaran tidak ditemukan.")
    return {"status": "success", "message": "Data pendaftaran dan file foto berhasil dihapus permanen (Right to Erasure)."}

import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from config.db import get_db
from schemas.alumni_profile import AlumniProfileResponse, AlumniProfileUpdate
from schemas.member import (
    GrantERPAccessRequest,
    MemberCreate,
    MemberResponse,
    MemberUpdate,
    ResetMemberPasswordRequest,
)
from services.member_service import MemberService
from utils.auth_deps import can_manage_members, require_pengurus
from utils.excel_importer import ExcelMemberImporter

router = APIRouter(prefix="/members", tags=["Members & Alumni"])


@router.get("/", response_model=list[MemberResponse])
async def list_members(
    division: str | None = None,
    intake_period: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_pengurus),
):
    """List all registered KSM AIoT members. Enforced RBAC: Pengurus only (Anggota Umum denied)."""
    service = MemberService(db)
    members = await service.get_all_members(division=division, intake_period=intake_period, member_status=status)
    return [MemberResponse.model_validate(m) for m in members]


@router.get("/{identifier}/alumni-profile", response_model=AlumniProfileResponse | None)
async def get_alumni_profile(
    identifier: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_pengurus),
):
    service = MemberService(db)
    profile = await service.get_alumni_profile(identifier)
    if profile is None:
        member = await service.get_member_by_identifier(identifier)
        if not member:
            raise HTTPException(status_code=404, detail="Data anggota tidak ditemukan")
    return profile


@router.put("/{identifier}/alumni-profile", response_model=AlumniProfileResponse)
async def update_alumni_profile(
    identifier: str,
    payload: AlumniProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(can_manage_members),
):
    service = MemberService(db)
    profile_data = payload.model_dump()
    if profile_data.get("linkedin_url") is not None:
        profile_data["linkedin_url"] = str(profile_data["linkedin_url"])
    profile = await service.upsert_alumni_profile(identifier, profile_data, actor=current_user)
    return AlumniProfileResponse.model_validate(profile)


@router.post("/", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def create_member(
    payload: MemberCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(can_manage_members),
):
    """
    Create or manually register a new KSM AIoT member.
    Enforced RBAC: Superadmin, Ketua, Wakil Ketua, or PSDM Division.
    """
    service = MemberService(db)
    member = await service.create_member(payload.model_dump(), actor=current_user)
    return MemberResponse.model_validate(member)


@router.get("/count")
async def get_members_count(
    db: AsyncSession = Depends(get_db),
):
    """
    Public endpoint to get member statistics (total, active, alumni) for landing page without authentication.
    """
    service = MemberService(db)
    return await service.get_public_stats()


@router.get("/{identifier}", response_model=MemberResponse)
async def get_member(
    identifier: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_pengurus),
):
    """Get single member by UUID, member_id (e.g. AIOT-2026-001) or student_id (NIM). Enforced RBAC: Pengurus only."""
    service = MemberService(db)
    member = await service.get_member_by_identifier(identifier)
    if not member:
        raise HTTPException(status_code=404, detail="Data anggota tidak ditemukan")
    return MemberResponse.model_validate(member)


@router.put("/{identifier}", response_model=MemberResponse)
async def update_member(
    identifier: str,
    payload: MemberUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(can_manage_members),
):
    """
    Update existing member data by UUID, member_id or student_id.
    Enforced RBAC: Superadmin, Ketua, Wakil Ketua, or PSDM Division.
    """
    service = MemberService(db)
    updated = await service.update_member(identifier, payload.model_dump(exclude_unset=True), actor=current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Data anggota tidak ditemukan")
    return MemberResponse.model_validate(updated)


@router.post("/{identifier}/anonymize", response_model=MemberResponse)
async def anonymize_member(
    identifier: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(can_manage_members),
):
    """
    Anonymize member data per UU PDP Right to Erasure while keeping relational integrity.
    Enforced RBAC: Superadmin, Ketua, Wakil Ketua, or PSDM Division.
    """
    service = MemberService(db)
    anonymized = await service.anonymize_member(identifier, actor=current_user)
    if not anonymized:
        raise HTTPException(status_code=404, detail="Data anggota tidak ditemukan")
    return MemberResponse.model_validate(anonymized)


@router.delete("/{identifier}")
async def delete_member(
    identifier: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(can_manage_members),
):
    """
    Hard delete member from database by UUID, member_id or student_id.
    Enforced RBAC: Superadmin, Ketua, Wakil Ketua, or PSDM Division.
    """
    service = MemberService(db)
    success = await service.delete_member(identifier, actor=current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Data anggota tidak ditemukan")
    return {"status": "success", "message": f"Anggota {identifier} berhasil dihapus permanen"}


@router.post("/import-excel")
async def import_members_excel(
    file: UploadFile = File(...),
    sheet_name: str = "Database Anggota",
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(can_manage_members),
):
    """
    Upload and import members spreadsheet into PostgreSQL using raw SQL.
    Enforced RBAC: SUPERADMIN or ADMIN_BPH.
    """
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Format file harus berupa Excel (.xlsx / .xls)")

    content = await file.read()
    file_bytes = io.BytesIO(content)
    try:
        members_data = ExcelMemberImporter.parse_excel(file_bytes, sheet_name=sheet_name)
        result = await ExcelMemberImporter.import_to_database(db, members_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memproses Excel: {e!s}") from e


@router.post("/{identifier}/access")
async def grant_erp_access(
    identifier: str,
    payload: GrantERPAccessRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(can_manage_members),
):
    """
    Grant or activate ERP dashboard login access for a member.
    Enforced RBAC: Superadmin, Ketua, Wakil Ketua, or PSDM Division.
    """
    service = MemberService(db)
    return await service.grant_erp_access(
        identifier=identifier,
        password=payload.password,
        erp_role=payload.role,
        actor=current_user,
    )


@router.delete("/{identifier}/access")
async def revoke_erp_access(
    identifier: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(can_manage_members),
):
    """
    Revoke/deactivate ERP login access for a member (e.g. when demisioner).
    Enforced RBAC: Superadmin, Ketua, Wakil Ketua, or PSDM Division.
    """
    service = MemberService(db)
    return await service.revoke_erp_access(identifier=identifier, actor=current_user)


@router.post("/{identifier}/reset-password")
async def reset_erp_password(
    identifier: str,
    payload: ResetMemberPasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(can_manage_members),
):
    """
    Reset ERP password for a member's login account.
    Enforced RBAC: Superadmin, Ketua, Wakil Ketua, or PSDM Division.
    """
    service = MemberService(db)
    return await service.reset_erp_password(
        identifier=identifier,
        new_password=payload.new_password,
        actor=current_user,
    )

import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from config.db import get_db
from schemas.member import MemberCreate, MemberResponse, MemberUpdate
from services.member_service import MemberService
from utils.auth_deps import can_manage_members, require_pengurus
from utils.excel_importer import ExcelMemberImporter

router = APIRouter(prefix="/members", tags=["Members & Alumni"])


@router.get("/", response_model=list[MemberResponse])
async def list_members(
    division: str | None = None,
    intake_period: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_pengurus),
):
    """List all registered KSM AIoT members. Enforced RBAC: Pengurus only (Anggota Umum denied)."""
    service = MemberService(db)
    members = await service.get_all_members(division=division, intake_period=intake_period)
    return [MemberResponse.model_validate(m) for m in members]


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

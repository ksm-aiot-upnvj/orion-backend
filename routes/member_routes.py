import io
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from config.db import get_db
from schemas.member import MemberResponse
from services.member_service import MemberService
from utils.excel_importer import ExcelMemberImporter

router = APIRouter(prefix="/members", tags=["Members & Alumni"])


@router.get("/", response_model=list[MemberResponse])
async def list_members(
    division: str | None = None,
    intake_period: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    """List all registered KSM AIoT members using raw SQL."""
    service = MemberService(db)
    members = await service.get_all_members(division=division, intake_period=intake_period)
    return [MemberResponse.model_validate(m) for m in members]


@router.get("/{identifier}", response_model=MemberResponse)
async def get_member(
    identifier: str,
    db: AsyncSession = Depends(get_db)
):
    """Get single member by UUID, member_id (e.g. AIOT-2026-001) or student_id (NIM) using raw SQL."""
    service = MemberService(db)
    member = await service.get_member_by_identifier(identifier)
    if not member:
        raise HTTPException(status_code=404, detail="Data anggota tidak ditemukan")
    return MemberResponse.model_validate(member)


@router.post("/import-excel")
async def import_members_excel(
    file: UploadFile = File(...),
    sheet_name: str = "Database Anggota",
    db: AsyncSession = Depends(get_db)
):
    """Upload and import members spreadsheet into PostgreSQL using raw SQL."""
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Format file harus berupa Excel (.xlsx / .xls)")

    content = await file.read()
    file_bytes = io.BytesIO(content)
    try:
        members_data = ExcelMemberImporter.parse_excel(file_bytes, sheet_name=sheet_name)
        result = await ExcelMemberImporter.import_to_database(db, members_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memproses Excel: {str(e)}")

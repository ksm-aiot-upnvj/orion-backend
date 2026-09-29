from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from config.db import get_db
from schemas.log import AuditLogEntryOut, AuditLogPageOut
from services.audit_log_service import AuditLogService
from utils.auth_deps import require_pengurus

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])

@router.get("", response_model=AuditLogPageOut)
async def get_audit_logs(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: None = Depends(require_pengurus),
):
    """
    Retrieve audit logs with pagination.
    Only accessible to users with 'pengurus' role.
    """
    service = AuditLogService(db)
    rows, stats = await service.get_logs(limit=limit, offset=offset), await service.get_log_stats()
    return AuditLogPageOut(
        items=[AuditLogEntryOut(**row) for row in rows],
        total=stats["total"],
        stats=stats,
    )

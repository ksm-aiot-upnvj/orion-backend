import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from utils.uuid_utils import generate_uuid7

logger = logging.getLogger("orion.audit")


class AuditLogService:
    """
    Centralized, async service for recording and retrieving audit logs across all ORION modules.
    Follows UU PDP Article 35 (Security & Audit Trail) and OWASP ASVS V7 (Audit Logging).
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_event(
        self,
        action: str,
        resource_type: str,
        actor_id: uuid.UUID | str | None = None,
        actor_name: str | None = None,
        actor_role: str | None = None,
        resource_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict[str, Any] | str | None = None,
        status: str = "SUCCESS",
    ) -> dict | None:
        """
        Record an immutable audit log entry into the database.
        Fails gracefully with logger warning if database write encounters an issue.
        """
        try:
            log_id = generate_uuid7()
            now = datetime.now(UTC)

            # Normalize actor_id
            parsed_actor_id = None
            if actor_id:
                try:
                    parsed_actor_id = uuid.UUID(str(actor_id))
                except (ValueError, AttributeError):
                    parsed_actor_id = None

            # Serialize details to JSON string if dict
            details_str = None
            if isinstance(details, dict):
                try:
                    details_str = json.dumps(details, default=str)
                except (TypeError, ValueError):
                    details_str = str(details)
            elif details is not None:
                details_str = str(details)

            stmt = text(
                """
                INSERT INTO audit_logs (
                    id, timestamp, actor_id, actor_name, actor_role, action,
                    resource_type, resource_id, ip_address, user_agent, details, status
                )
                VALUES (
                    :id, :timestamp, :actor_id, :actor_name, :actor_role, :action,
                    :resource_type, :resource_id, :ip_address, :user_agent, :details, :status
                )
                RETURNING id, timestamp, actor_id, actor_name, actor_role, action, resource_type, resource_id, status
                """
            )

            params = {
                "id": log_id,
                "timestamp": now,
                "actor_id": parsed_actor_id,
                "actor_name": actor_name or "ANONYMOUS/SYSTEM",
                "actor_role": actor_role or "SYSTEM",
                "action": action.upper(),
                "resource_type": resource_type.upper(),
                "resource_id": str(resource_id) if resource_id is not None else None,
                "ip_address": ip_address,
                "user_agent": user_agent[:255] if user_agent else None,
                "details": details_str,
                "status": status.upper(),
            }

            result = await self.session.execute(stmt, params)
            await self.session.commit()
            return result.mappings().first()

        except Exception as e:
            logger.error("Gagal mencatat audit log: %s | Action: %s | Resource: %s", e, action, resource_type)
            return None

    async def get_logs(
        self,
        resource_type: str | None = None,
        action: str | None = None,
        actor_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Query audit logs with optional filtering and pagination."""
        query_str = """
            SELECT id, timestamp, actor_id, actor_name, actor_role, action,
                   resource_type, resource_id, ip_address, user_agent, details, status
            FROM audit_logs
            WHERE 1=1
        """
        params: dict[str, Any] = {"limit": min(limit, 200), "offset": max(offset, 0)}

        if resource_type:
            query_str += " AND resource_type = :resource_type"
            params["resource_type"] = resource_type.upper()
        if action:
            query_str += " AND action = :action"
            params["action"] = action.upper()
        if actor_id:
            try:
                params["actor_id"] = uuid.UUID(actor_id)
                query_str += " AND actor_id = :actor_id"
            except ValueError:
                pass

        query_str += " ORDER BY timestamp DESC LIMIT :limit OFFSET :offset"

        result = await self.session.execute(text(query_str), params)
        return result.mappings().all()


async def log_audit_event(
    session: AsyncSession,
    action: str,
    resource_type: str,
    actor_id: uuid.UUID | str | None = None,
    actor_name: str | None = None,
    actor_role: str | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | str | None = None,
    status: str = "SUCCESS",
) -> dict | None:
    """Convenience helper function to log an audit event from any route/service."""
    service = AuditLogService(session)
    return await service.log_event(
        action=action,
        resource_type=resource_type,
        actor_id=actor_id,
        actor_name=actor_name,
        actor_role=actor_role,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
        status=status,
    )

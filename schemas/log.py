import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogEntry(BaseModel):
    id: uuid.UUID
    timestamp: datetime
    actor_id: uuid.UUID | None = None
    actor_name: str | None = None
    actor_role: str | None = None
    is_superadmin: bool | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    resource_label: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    details: dict[str, Any] | str | None = None
    status: str

    model_config = ConfigDict(from_attributes=True)

class AuditLogEntryCreate(BaseModel):
    action: str
    resource_type: str
    actor_id: uuid.UUID | None = None
    actor_name: str | None = None
    actor_role: str | None = None
    resource_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    details: dict[str, Any] | str | None = None
    status: str = "SUCCESS"

class AuditLogEntryOut(AuditLogEntry):
    model_config = ConfigDict(from_attributes=True)


class AuditLogPageOut(BaseModel):
    items: list[AuditLogEntryOut]
    total: int
    stats: dict[str, int]

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID

from config.db import Base
from utils.uuid_utils import generate_uuid7


class AuditLog(Base):
    """
    Append-Only Audit Log Table (UU PDP, GDPR & OWASP ASVS Compliant).
    Shared across all ORION modules: Auth, Members, Recruitment, Inventory, Finance, Archive.
    Database-level triggers prevent UPDATE and DELETE operations.
    """
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid7)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True)
    actor_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    actor_name = Column(String(150), nullable=True)
    actor_role = Column(String(50), nullable=True)
    action = Column(String(100), nullable=False, index=True)  # e.g., AUTH_LOGIN, REGISTRATION_APPROVED, MEMBER_DELETED
    resource_type = Column(String(50), nullable=False, index=True)  # e.g., USER, MEMBER, REGISTRATION, FINANCE, INVENTORY
    resource_id = Column(String(100), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    details = Column(Text, nullable=True)  # JSON-encoded details or unstructured audit context
    status = Column(String(20), default="SUCCESS", nullable=False)  # SUCCESS, FAILED, DENIED

from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID

from config.db import Base
from utils.uuid_utils import generate_uuid7


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid7)
    student_id = Column(String(20), unique=True, index=True, nullable=False)  # NIM
    full_name = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="PENGURUS", nullable=False)  # SUPERADMIN, ADMIN_BPH, PENGURUS
    division = Column(String(100), nullable=False)  # BPH, Akademik & Riset, Pengembangan SDM, Humas & Multimedia
    avatar = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

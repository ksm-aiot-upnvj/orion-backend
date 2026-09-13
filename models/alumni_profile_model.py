from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID

from config.db import Base
from utils.uuid_utils import generate_uuid7


class AlumniProfile(Base):
    __tablename__ = "alumni_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid7)
    member_id = Column(UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), unique=True, nullable=False)
    graduation_year = Column(String(4), nullable=True)
    current_company = Column(String(150), nullable=True)
    current_role = Column(String(150), nullable=True)
    linkedin_url = Column(Text, nullable=True)
    testimonial = Column(Text, nullable=True)
    visibility = Column(Boolean, nullable=False, default=False)
    consent_given = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

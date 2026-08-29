from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID

from config.db import Base
from utils.uuid_utils import generate_uuid7


class Registration(Base):
    __tablename__ = "registrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid7)
    student_id = Column(String(20), unique=True, index=True, nullable=False)  # NIM
    full_name = Column(String(150), nullable=False)
    program_of_study = Column(String(100), nullable=False)
    email = Column(String(150), nullable=False)
    contact_info = Column(String(50), nullable=True)
    intake_period = Column(String(20), nullable=False)  # Angkatan
    interest_track = Column(String(100), nullable=False)
    motivation = Column(Text, nullable=True)
    photo = Column(Text, nullable=True)  # Base64 or Image URL
    status = Column(String(50), default="PENDING")  # PENDING, APPROVED, REJECTED
    member_id = Column(String(50), nullable=True)
    review_note = Column(Text, nullable=True)
    submit_date = Column(String(30), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)

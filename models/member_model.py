from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from config.db import Base
from utils.uuid_utils import generate_uuid7


class Member(Base):
    __tablename__ = "members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid7)
    member_id = Column(String(50), unique=True, index=True, nullable=False)  # Business ID: AIOT-2026-001
    student_id = Column(String(20), unique=True, index=True, nullable=False)  # NIM
    full_name = Column(String(150), nullable=False)
    program_of_study = Column(String(100), nullable=False)
    semester = Column(Integer, nullable=True)
    email = Column(String(150), nullable=False)
    contact_info = Column(String(50), nullable=True)  # No WhatsApp
    domicile_city = Column(String(100), nullable=True)
    division = Column(String(100), nullable=False)
    role = Column(String(100), nullable=False)
    intake_period = Column(String(20), nullable=False)  # Tahun Masuk KSM / Angkatan
    interest_track = Column(String(255), nullable=True)
    focus_expertise = Column(Text, nullable=True)
    exploration_field = Column(Text, nullable=True)
    field_reason = Column(Text, nullable=True)
    programming_languages = Column(Text, nullable=True)
    tools_frameworks = Column(Text, nullable=True)
    project_experience = Column(Text, nullable=True)
    hackathon_experience = Column(String(100), nullable=True)
    portfolio_url = Column(Text, nullable=True)
    routine_commitment = Column(String(50), nullable=True)
    weekly_free_time = Column(String(50), nullable=True)
    other_activities = Column(Text, nullable=True)
    discord_id = Column(String(100), nullable=True)
    registration_timestamp = Column(String(50), nullable=True)
    avatar = Column(String(500), nullable=True)
    status = Column(String(50), default="Aktif")
    join_date = Column(String(30), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

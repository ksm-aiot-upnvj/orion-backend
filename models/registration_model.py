from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum

from config.db import Base
from models.enums import ResearchField, SelectionStatus, StudyProgram
from utils.uuid_utils import generate_uuid7


class Registration(Base):
    __tablename__ = "registrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid7)
    student_id = Column(String(20), unique=True, index=True, nullable=False)  # NIM
    full_name = Column(String(150), nullable=False)
    program_of_study = Column(
        PgEnum(StudyProgram, name="study_program_enum", values_callable=lambda obj: [e.value for e in obj], create_type=False),
        nullable=False,
    )
    email = Column(String(150), nullable=False)
    contact_info = Column(String(50), nullable=True)
    intake_period = Column(String(20), nullable=False)  # Angkatan
    interest_track = Column(
        ARRAY(PgEnum(ResearchField, name="research_field_enum", values_callable=lambda obj: [e.value for e in obj], create_type=False)),
        nullable=True,
    )
    motivation = Column(Text, nullable=True)
    photo = Column(String(255), nullable=True)  # Stores relative path 'avatars/<uuid4>.webp'
    status = Column(
        PgEnum(SelectionStatus, name="selection_status_enum", values_callable=lambda obj: [e.value for e in obj], create_type=False),
        default=SelectionStatus.PENDING,
        nullable=False,
    )
    member_id = Column(String(50), nullable=True)
    review_note = Column(Text, nullable=True)
    submit_date = Column(String(30), nullable=True)
    consent_given = Column(Boolean, default=True, nullable=False)  # UU PDP No. 27/2022 Explicit Consent
    consent_timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)

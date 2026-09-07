import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from models.enums import Division, MemberRole, ResearchField, SelectionStatus, StudyProgram


class RegistrationCreate(BaseModel):
    student_id: str
    full_name: str
    program_of_study: StudyProgram
    email: str
    contact_info: str | None = None
    intake_period: str = "2026"
    interest_track: list[ResearchField] = [ResearchField.AI]
    motivation: str | None = None
    photo: str | None = None
    consent_given: bool = True

    @field_validator("motivation")
    @classmethod
    def validate_motivation(cls, v: str | None) -> str | None:
        if not v:
            return v
        import re
        text_clean = v.strip()
        # Count sentences: split by ., !, ?
        sentences = [s.strip() for s in re.split(r"[.!?]+", text_clean) if s.strip()]
        if len(sentences) > 3:
            raise ValueError("Teks motivasi maksimal terdiri dari 3 kalimat.")
        words = [w for w in text_clean.split() if w.strip()]
        if len(words) > 100:
            raise ValueError("Teks motivasi maksimal terdiri dari 100 kata.")
        return v

    @field_validator("interest_track", mode="before")
    @classmethod
    def parse_interest_track(cls, v: Any) -> list[ResearchField]:
        if isinstance(v, str):
            items = [item.strip() for item in v.split(",") if item.strip()]
            resolved = []
            for item in items:
                for rf in ResearchField:
                    if rf.value.lower() == item.lower() or rf.name.lower() == item.lower():
                        resolved.append(rf)
                        break
                else:
                    if "iot" in item.lower() or "embedded" in item.lower():
                        resolved.append(ResearchField.IOT_EMBEDDED)
                    elif "ai" in item.lower() or "ml" in item.lower() or "artificial" in item.lower():
                        resolved.append(ResearchField.AI)
                    elif "cloud" in item.lower() or "software" in item.lower() or "web" in item.lower():
                        resolved.append(ResearchField.SOFTWARE_ENGINEER_CLOUD)
            return resolved or [ResearchField.AI]
        if isinstance(v, list):
            return v
        return [ResearchField.AI]


class IntakeStatusResponse(BaseModel):
    status: str
    batch_name: str
    deadline: str
    quota: int
    updated_at: datetime | None = None
    updated_by: uuid.UUID | None = None


class IntakeStatusUpdate(BaseModel):
    status: str  # OPEN or CLOSED
    batch_name: str
    deadline: str  # YYYY-MM-DD
    quota: int = 100


class RegistrationReview(BaseModel):
    status: SelectionStatus  # Accepted or Rejected
    review_note: str | None = None
    division: Division | None = None
    role: MemberRole | None = MemberRole.ANGGOTA


class RegistrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_id: str
    full_name: str
    program_of_study: StudyProgram
    email: str
    contact_info: str | None = None
    intake_period: str
    interest_track: list[ResearchField] | None = None
    motivation: str | None = None
    photo: str | None = None
    status: SelectionStatus
    member_id: str | None = None
    review_note: str | None = None
    submit_date: str | None = None
    consent_given: bool = True
    consent_timestamp: datetime | None = None

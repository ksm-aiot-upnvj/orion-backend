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

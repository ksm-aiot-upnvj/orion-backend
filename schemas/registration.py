import uuid

from pydantic import BaseModel, ConfigDict


class RegistrationCreate(BaseModel):
    student_id: str
    full_name: str
    program_of_study: str
    email: str
    contact_info: str | None = None
    intake_period: str = "2024"
    interest_track: str = "Artificial Intelligence & ML"
    motivation: str | None = None
    photo: str | None = None

class RegistrationReview(BaseModel):
    status: str  # APPROVED or REJECTED
    review_note: str | None = None
    division: str | None = "Akademik & Riset"
    role: str | None = "Anggota Muda"

class RegistrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_id: str
    full_name: str
    program_of_study: str
    email: str
    contact_info: str | None = None
    intake_period: str
    interest_track: str
    motivation: str | None = None
    photo: str | None = None
    status: str
    member_id: str | None = None
    review_note: str | None = None
    submit_date: str | None = None

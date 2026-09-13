import uuid

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class AlumniProfileBase(BaseModel):
    graduation_year: str | None = Field(default=None, pattern=r"^\d{4}$")
    current_company: str | None = None
    current_role: str | None = None
    linkedin_url: HttpUrl | None = None
    testimonial: str | None = None
    visibility: bool = False
    consent_given: bool = False


class AlumniProfileUpdate(AlumniProfileBase):
    pass


class AlumniProfileResponse(AlumniProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    member_id: uuid.UUID

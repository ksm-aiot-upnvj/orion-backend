import uuid
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class AlumniProfileBase(BaseModel):
    graduation_year: str | None = Field(default=None, pattern=r"^\d{4}$")
    current_company: str | None = Field(default=None, max_length=150)
    current_role: str | None = Field(default=None, max_length=150)
    linkedin_url: HttpUrl | None = None
    testimonial: str | None = None
    visibility: bool = False
    consent_given: bool = False


class AlumniProfileUpdate(AlumniProfileBase):
    @model_validator(mode="after")
    def require_publication_consent(self) -> Self:
        if self.visibility and not self.consent_given:
            raise ValueError("Persetujuan alumni diperlukan untuk publikasi.")
        return self


class AlumniProfileResponse(AlumniProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    member_id: uuid.UUID

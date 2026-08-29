import uuid
from pydantic import BaseModel, ConfigDict


class MemberBase(BaseModel):
    member_id: str
    student_id: str
    full_name: str
    program_of_study: str
    semester: int | None = None
    email: str
    contact_info: str | None = None
    domicile_city: str | None = None
    division: str
    role: str
    intake_period: str
    interest_track: str | None = None
    focus_expertise: str | None = None
    exploration_field: str | None = None
    field_reason: str | None = None
    programming_languages: str | None = None
    tools_frameworks: str | None = None
    project_experience: str | None = None
    hackathon_experience: str | None = None
    portfolio_url: str | None = None
    routine_commitment: str | None = None
    weekly_free_time: str | None = None
    other_activities: str | None = None
    discord_id: str | None = None
    registration_timestamp: str | None = None
    avatar: str | None = None
    status: str = "Aktif"
    join_date: str | None = None


class MemberCreate(MemberBase):
    pass


class MemberResponse(MemberBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID

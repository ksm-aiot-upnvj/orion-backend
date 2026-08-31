import uuid

from pydantic import BaseModel, ConfigDict

from models.enums import Division, MemberRole, MemberStatus, ResearchField, StudyProgram


class MemberBase(BaseModel):
    member_id: str
    student_id: str
    full_name: str
    program_of_study: StudyProgram
    semester: int | None = None
    email: str
    contact_info: str | None = None
    domicile_city: str | None = None
    division: Division | None = None
    role: MemberRole
    intake_period: str
    interest_track: list[ResearchField] | None = None
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
    status: MemberStatus = MemberStatus.AKTIF
    join_date: str | None = None


class MemberCreate(BaseModel):
    member_id: str | None = None
    student_id: str
    full_name: str
    program_of_study: StudyProgram
    semester: int | None = None
    email: str
    contact_info: str | None = None
    domicile_city: str | None = None
    division: Division | None = None
    role: MemberRole = MemberRole.ANGGOTA
    intake_period: str = "2026"
    interest_track: list[ResearchField] | None = None
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
    status: MemberStatus = MemberStatus.AKTIF
    join_date: str | None = None


class MemberUpdate(BaseModel):
    full_name: str | None = None
    program_of_study: StudyProgram | None = None
    semester: int | None = None
    email: str | None = None
    contact_info: str | None = None
    domicile_city: str | None = None
    division: Division | None = None
    role: MemberRole | None = None
    intake_period: str | None = None
    interest_track: list[ResearchField] | None = None
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
    avatar: str | None = None
    status: MemberStatus | None = None
    join_date: str | None = None


class MemberResponse(MemberBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID



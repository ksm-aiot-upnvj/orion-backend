import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from utils.uuid_utils import generate_uuid7


class MemberService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_members(self, division: str | None = None, intake_period: str | None = None) -> list[dict]:
        """Fetch all members using raw parameterized SQL."""
        query_str = """
            SELECT id, member_id, student_id, full_name, program_of_study, semester, email, contact_info, domicile_city,
                   division, role, intake_period, interest_track, focus_expertise, exploration_field, field_reason,
                   programming_languages, tools_frameworks, project_experience, hackathon_experience, portfolio_url,
                   routine_commitment, weekly_free_time, other_activities, discord_id, registration_timestamp,
                   avatar, status, join_date, created_at
            FROM members
            WHERE 1=1
        """
        params = {}

        if division and division != "all":
            query_str += " AND division = :division"
            params["division"] = division
        if intake_period and intake_period != "all":
            query_str += " AND intake_period = :intake_period"
            params["intake_period"] = intake_period

        query_str += " ORDER BY member_id ASC"

        result = await self.session.execute(text(query_str), params)
        return result.mappings().all()

    async def get_member_by_identifier(self, identifier: str) -> dict | None:
        """Fetch single member by UUID, member_id or student_id using raw parameterized SQL."""
        try:
            member_uuid = uuid.UUID(identifier)
            stmt = text("SELECT * FROM members WHERE id = :uuid")
            result = await self.session.execute(stmt, {"uuid": member_uuid})
            return result.mappings().first()
        except ValueError:
            stmt = text("SELECT * FROM members WHERE member_id = :identifier OR student_id = :identifier")
            result = await self.session.execute(stmt, {"identifier": identifier})
            return result.mappings().first()

    async def count_members(self) -> int:
        """Count total members using raw SQL."""
        stmt = text("SELECT COUNT(*) AS total FROM members")
        result = await self.session.execute(stmt)
        row = result.mappings().first()
        return row["total"] if row else 0

    async def create_member(self, member_data: dict) -> dict:
        """Insert or update member using raw SQL RETURNING *."""
        member_id = member_data.get("id", generate_uuid7())
        stmt = text(
            """
            INSERT INTO members (
                id, member_id, student_id, full_name, program_of_study, semester, email, contact_info, domicile_city,
                division, role, intake_period, interest_track, focus_expertise, exploration_field, field_reason,
                programming_languages, tools_frameworks, project_experience, hackathon_experience, portfolio_url,
                routine_commitment, weekly_free_time, other_activities, discord_id, registration_timestamp,
                avatar, status, join_date, created_at
            )
            VALUES (
                :id, :member_id, :student_id, :full_name, :program_of_study, :semester, :email, :contact_info, :domicile_city,
                :division, :role, :intake_period, :interest_track, :focus_expertise, :exploration_field, :field_reason,
                :programming_languages, :tools_frameworks, :project_experience, :hackathon_experience, :portfolio_url,
                :routine_commitment, :weekly_free_time, :other_activities, :discord_id, :registration_timestamp,
                :avatar, :status, :join_date, NOW()
            )
            ON CONFLICT (student_id) DO UPDATE SET
                member_id = EXCLUDED.member_id,
                full_name = EXCLUDED.full_name,
                program_of_study = EXCLUDED.program_of_study,
                semester = EXCLUDED.semester,
                email = EXCLUDED.email,
                contact_info = EXCLUDED.contact_info,
                domicile_city = EXCLUDED.domicile_city,
                division = EXCLUDED.division,
                role = EXCLUDED.role,
                intake_period = EXCLUDED.intake_period,
                interest_track = EXCLUDED.interest_track,
                focus_expertise = EXCLUDED.focus_expertise,
                exploration_field = EXCLUDED.exploration_field,
                field_reason = EXCLUDED.field_reason,
                programming_languages = EXCLUDED.programming_languages,
                tools_frameworks = EXCLUDED.tools_frameworks,
                project_experience = EXCLUDED.project_experience,
                hackathon_experience = EXCLUDED.hackathon_experience,
                portfolio_url = EXCLUDED.portfolio_url,
                routine_commitment = EXCLUDED.routine_commitment,
                weekly_free_time = EXCLUDED.weekly_free_time,
                other_activities = EXCLUDED.other_activities,
                discord_id = EXCLUDED.discord_id,
                registration_timestamp = EXCLUDED.registration_timestamp,
                avatar = EXCLUDED.avatar,
                status = EXCLUDED.status,
                join_date = EXCLUDED.join_date
            RETURNING *
            """
        )
        params = {
            "id": member_id,
            "member_id": member_data["member_id"],
            "student_id": str(member_data["student_id"]),
            "full_name": member_data["full_name"],
            "program_of_study": member_data.get("program_of_study", "-"),
            "semester": member_data.get("semester"),
            "email": member_data.get("email", "-"),
            "contact_info": member_data.get("contact_info"),
            "domicile_city": member_data.get("domicile_city"),
            "division": member_data.get("division", "BPH"),
            "role": member_data.get("role", "Anggota"),
            "intake_period": str(member_data.get("intake_period", "2026")),
            "interest_track": member_data.get("interest_track"),
            "focus_expertise": member_data.get("focus_expertise"),
            "exploration_field": member_data.get("exploration_field"),
            "field_reason": member_data.get("field_reason"),
            "programming_languages": member_data.get("programming_languages"),
            "tools_frameworks": member_data.get("tools_frameworks"),
            "project_experience": member_data.get("project_experience"),
            "hackathon_experience": member_data.get("hackathon_experience"),
            "portfolio_url": member_data.get("portfolio_url"),
            "routine_commitment": member_data.get("routine_commitment"),
            "weekly_free_time": member_data.get("weekly_free_time"),
            "other_activities": member_data.get("other_activities"),
            "discord_id": member_data.get("discord_id"),
            "registration_timestamp": member_data.get("registration_timestamp"),
            "avatar": member_data.get("avatar"),
            "status": member_data.get("status", "Aktif"),
            "join_date": member_data.get("join_date"),
        }
        result = await self.session.execute(stmt, params)
        await self.session.commit()
        return result.mappings().first()

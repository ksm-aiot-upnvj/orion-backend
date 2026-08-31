import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from models.enums import MemberRole, MemberStatus, StudyProgram
from services.audit_log_service import log_audit_event
from services.storage_service import StorageService
from utils.sanitizer import sanitize_dict_fields
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
            if division == "none":
                query_str += " AND division IS NULL"
            else:
                query_str += " AND division = :division"
                params["division"] = division
        if intake_period and intake_period != "all":
            query_str += " AND intake_period = :intake_period"
            params["intake_period"] = intake_period

        query_str += " ORDER BY created_at ASC"

        result = await self.session.execute(text(query_str), params)
        return result.mappings().all()

    async def get_member_by_identifier(self, identifier: str) -> dict | None:
        """Find member by UUID, member_id or student_id."""
        try:
            val_uuid = uuid.UUID(identifier)
            stmt = text("SELECT * FROM members WHERE id = :id")
            result = await self.session.execute(stmt, {"id": val_uuid})
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

    async def create_member(self, member_data: dict, actor: dict | None = None) -> dict:
        """Insert or update member using raw SQL RETURNING * with sanitization and audit logging."""
        # Sanitize text fields to prevent injection
        member_data = sanitize_dict_fields(member_data)

        m_id = member_data.get("id", generate_uuid7())
        member_id = member_data.get("member_id")
        if not member_id:
            count = await self.count_members()
            intake_raw = str(member_data.get("intake_period") or "").strip()
            student_id_raw = str(member_data.get("student_id") or "").strip()
            if intake_raw.isdigit() and len(intake_raw) == 4:
                year = intake_raw
            elif intake_raw.isdigit() and len(intake_raw) == 2:
                year = f"20{intake_raw}"
            elif len(student_id_raw) >= 2 and student_id_raw[:2].isdigit():
                year = f"20{student_id_raw[:2]}"
            else:
                year = str(datetime.now().year)
            member_id = f"AIOT-{year}-{str(count + 1).zfill(3)}"

        # Normalize enum/array values
        def get_enum_val(v, default_val):
            if v is None:
                return default_val
            return v.value if hasattr(v, "value") else str(v)

        prodi = get_enum_val(member_data.get("program_of_study"), StudyProgram.S1_INFORMATIKA.value)
        div = get_enum_val(member_data.get("division"), None)
        role = get_enum_val(member_data.get("role"), MemberRole.ANGGOTA.value)
        stat = get_enum_val(member_data.get("status"), MemberStatus.AKTIF.value)

        tracks = member_data.get("interest_track")
        if isinstance(tracks, str):
            tracks = [tracks]
        elif tracks is not None:
            tracks = [t.value if hasattr(t, "value") else str(t) for t in tracks]

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
            "id": m_id,
            "member_id": member_id,
            "student_id": str(member_data["student_id"]),
            "full_name": member_data["full_name"],
            "program_of_study": prodi,
            "semester": member_data.get("semester"),
            "email": member_data.get("email", "-"),
            "contact_info": member_data.get("contact_info"),
            "domicile_city": member_data.get("domicile_city"),
            "division": div,
            "role": role,
            "intake_period": str(member_data.get("intake_period", "2026")),
            "interest_track": tracks,
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
            "status": stat,
            "join_date": member_data.get("join_date"),
        }
        result = await self.session.execute(stmt, params)
        await self.session.commit()
        created_row = result.mappings().first()

        if actor and created_row:
            await log_audit_event(
                session=self.session,
                action="MEMBER_CREATED",
                resource_type="MEMBER",
                resource_id=str(created_row["id"]),
                actor_id=actor.get("id"),
                actor_name=actor.get("full_name"),
                actor_role=actor.get("role"),
                details={"member_id": created_row["member_id"], "student_id": created_row["student_id"]},
            )

        return created_row

    async def update_member(self, identifier: str, update_data: dict, actor: dict | None = None) -> dict | None:
        """Update an existing member by UUID, member_id, or student_id."""
        existing = await self.get_member_by_identifier(identifier)
        if not existing:
            return None

        update_data = sanitize_dict_fields(update_data)
        fields = []
        params = {"id": existing["id"]}

        for k, v in update_data.items():
            if v is not None:
                if k == "program_of_study":
                    fields.append("program_of_study = :program_of_study")
                    params["program_of_study"] = v.value if hasattr(v, "value") else str(v)
                elif k == "division":
                    fields.append("division = :division")
                    params["division"] = v.value if hasattr(v, "value") else str(v)
                elif k == "role":
                    fields.append("role = :role")
                    params["role"] = v.value if hasattr(v, "value") else str(v)
                elif k == "status":
                    fields.append("status = :status")
                    params["status"] = v.value if hasattr(v, "value") else str(v)
                elif k == "interest_track":
                    fields.append("interest_track = :interest_track")
                    if isinstance(v, list):
                        params["interest_track"] = [t.value if hasattr(t, "value") else str(t) for t in v]
                    else:
                        params["interest_track"] = [v]
                else:
                    fields.append(f"{k} = :{k}")
                    params[k] = v

        if not fields:
            return existing

        stmt = text(f"UPDATE members SET {', '.join(fields)} WHERE id = :id RETURNING *")
        result = await self.session.execute(stmt, params)
        await self.session.commit()
        updated_row = result.mappings().first()

        if actor and updated_row:
            await log_audit_event(
                session=self.session,
                action="MEMBER_UPDATED",
                resource_type="MEMBER",
                resource_id=str(updated_row["id"]),
                actor_id=actor.get("id"),
                actor_name=actor.get("full_name"),
                actor_role=actor.get("role"),
                details={"updated_fields": list(update_data.keys())},
            )

        return updated_row

    async def anonymize_member(self, identifier: str, actor: dict | None = None) -> dict | None:
        """
        Anonymize member PII while preserving ID and historical links for Kas/Inventaris/Surat (UU PDP Right to Erasure).
        """
        existing = await self.get_member_by_identifier(identifier)
        if not existing:
            return None

        # 1. Physically delete avatar file from storage
        if existing.get("avatar"):
            StorageService().delete_avatar(existing["avatar"])

        anon_suffix = uuid.uuid4().hex[:8]
        stmt = text(
            """
            UPDATE members
            SET full_name = '[DELETED USER]',
                email = :anon_email,
                contact_info = NULL,
                domicile_city = NULL,
                discord_id = NULL,
                avatar = NULL,
                status = :status,
                focus_expertise = NULL,
                exploration_field = NULL,
                field_reason = NULL,
                portfolio_url = NULL,
                other_activities = NULL
            WHERE id = :id
            RETURNING *
            """
        )
        params = {
            "id": existing["id"],
            "anon_email": f"deleted_{anon_suffix}@anonymized.orion",
            "status": MemberStatus.TIDAK_AKTIF.value,
        }
        result = await self.session.execute(stmt, params)
        await self.session.commit()
        anonymized_row = result.mappings().first()

        if actor:
            await log_audit_event(
                session=self.session,
                action="MEMBER_ANONYMIZED",
                resource_type="MEMBER",
                resource_id=str(existing["id"]),
                actor_id=actor.get("id"),
                actor_name=actor.get("full_name"),
                actor_role=actor.get("role"),
                details={"member_id": existing["member_id"], "reason": "UU PDP Right to Erasure / Anonymization"},
            )

        return anonymized_row

    async def delete_member(self, identifier: str, actor: dict | None = None) -> bool:
        """Hard delete member by identifier and unlink physical avatar (Right to Erasure)."""
        existing = await self.get_member_by_identifier(identifier)
        if not existing:
            return False

        if existing.get("avatar"):
            StorageService().delete_avatar(existing["avatar"])

        stmt = text("DELETE FROM members WHERE id = :id")
        await self.session.execute(stmt, {"id": existing["id"]})
        await self.session.commit()

        if actor:
            await log_audit_event(
                session=self.session,
                action="MEMBER_DELETED",
                resource_type="MEMBER",
                resource_id=str(existing["id"]),
                actor_id=actor.get("id"),
                actor_name=actor.get("full_name"),
                actor_role=actor.get("role"),
                details={"member_id": existing["member_id"], "student_id": existing["student_id"]},
            )

        return True

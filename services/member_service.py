import uuid

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from models.enums import MemberRole, MemberStatus, StudyProgram
from services.audit_log_service import log_audit_event
from services.member_id import member_id_year, next_member_id
from services.storage_service import StorageService, release_upload
from utils.auth_deps import is_superadmin_user
from utils.sanitizer import sanitize_dict_fields
from utils.security import hash_password
from utils.uuid_utils import generate_uuid7

ERP_ROLE_PENGURUS = "PENGURUS"
ERP_ROLE_SUPERADMIN = "SUPERADMIN"
ERP_ROLES = {ERP_ROLE_PENGURUS, ERP_ROLE_SUPERADMIN}
# Member fields that feed RBAC decisions (utils/auth_deps.py)
PRIVILEGED_MEMBER_FIELDS = ("role", "division", "status")


class MemberService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_members(
        self,
        division: str | None = None,
        intake_period: str | None = None,
        member_status: str | None = None,
    ) -> list[dict]:
        """Fetch all members with ERP access status using raw parameterized SQL."""
        query_str = """
            SELECT m.id, m.member_id, m.student_id, m.full_name, m.program_of_study, m.semester, m.email, m.contact_info, m.domicile_city,
                   m.division, m.role, m.intake_period, m.interest_track, m.focus_expertise, m.exploration_field, m.field_reason,
                   m.programming_languages, m.tools_frameworks, m.project_experience, m.hackathon_experience, m.portfolio_url,
                   m.routine_commitment, m.weekly_free_time, m.other_activities, m.discord_id, m.registration_timestamp,
                   m.avatar, m.status, m.join_date, m.created_at,
                   (u.id IS NOT NULL AND u.is_active = true) AS has_erp_access,
                   u.role AS user_role,
                   u.is_active AS user_is_active
            FROM members m
            LEFT JOIN users u ON (m.id = u.member_id OR m.student_id = u.student_id)
            WHERE 1=1
        """
        params = {}

        if division and division != "all":
            if division == "none":
                query_str += " AND m.division IS NULL"
            else:
                query_str += " AND m.division = :division"
                params["division"] = division
        if intake_period and intake_period != "all":
            query_str += " AND m.intake_period = :intake_period"
            params["intake_period"] = intake_period
        if member_status and member_status != "all":
            query_str += " AND m.status = :member_status"
            params["member_status"] = member_status

        query_str += " ORDER BY m.created_at ASC"

        result = await self.session.execute(text(query_str), params)
        return result.mappings().all()

    async def get_alumni_profile(self, identifier: str) -> dict | None:
        member = await self.get_member_by_identifier(identifier)
        if not member:
            return None
        result = await self.session.execute(
            text("SELECT * FROM alumni_profiles WHERE member_id = :member_id"),
            {"member_id": member["id"]},
        )
        profile = result.mappings().first()
        return dict(profile) if profile else None

    async def upsert_alumni_profile(self, identifier: str, profile_data: dict, actor: dict | None = None) -> dict:
        member = await self.get_member_by_identifier(identifier)
        if not member:
            raise HTTPException(status_code=404, detail="Data anggota tidak ditemukan")
        if member["status"] != MemberStatus.ALUMNI.value:
            raise HTTPException(
                status_code=409, detail="Profil alumni hanya dapat diatur untuk anggota berstatus Alumni"
            )

        params = {
            "id": generate_uuid7(),
            "member_id": member["id"],
            **profile_data,
        }
        result = await self.session.execute(
            text(
                """
                INSERT INTO alumni_profiles (
                    id, member_id, graduation_year, current_company, current_role,
                    linkedin_url, testimonial, visibility, consent_given, created_at, updated_at
                ) VALUES (
                    :id, :member_id, :graduation_year, :current_company, :current_role,
                    :linkedin_url, :testimonial, :visibility, :consent_given, NOW(), NOW()
                )
                ON CONFLICT (member_id) DO UPDATE SET
                    graduation_year = EXCLUDED.graduation_year,
                    current_company = EXCLUDED.current_company,
                    current_role = EXCLUDED.current_role,
                    linkedin_url = EXCLUDED.linkedin_url,
                    testimonial = EXCLUDED.testimonial,
                    visibility = EXCLUDED.visibility,
                    consent_given = EXCLUDED.consent_given,
                    updated_at = NOW()
                RETURNING *
                """
            ),
            params,
        )
        await self.session.commit()
        return dict(result.mappings().first())

    async def get_member_by_identifier(self, identifier: str) -> dict | None:
        """Find member by UUID, member_id or student_id with ERP access info."""
        base_query = """
            SELECT m.id, m.member_id, m.student_id, m.full_name, m.program_of_study, m.semester, m.email, m.contact_info, m.domicile_city,
                   m.division, m.role, m.intake_period, m.interest_track, m.focus_expertise, m.exploration_field, m.field_reason,
                   m.programming_languages, m.tools_frameworks, m.project_experience, m.hackathon_experience, m.portfolio_url,
                   m.routine_commitment, m.weekly_free_time, m.other_activities, m.discord_id, m.registration_timestamp,
                   m.avatar, m.status, m.join_date, m.created_at,
                   (u.id IS NOT NULL AND u.is_active = true) AS has_erp_access,
                   u.role AS user_role,
                   u.is_active AS user_is_active
            FROM members m
            LEFT JOIN users u ON (m.id = u.member_id OR m.student_id = u.student_id)
        """
        try:
            val_uuid = uuid.UUID(identifier)
            stmt = text(f"{base_query} WHERE m.id = :id")
            result = await self.session.execute(stmt, {"id": val_uuid})
            return result.mappings().first()
        except ValueError:
            stmt = text(f"{base_query} WHERE m.member_id = :identifier OR m.student_id = :identifier")
            result = await self.session.execute(stmt, {"identifier": identifier})
            return result.mappings().first()

    async def count_members(self) -> int:
        """Count total members using raw SQL."""
        stmt = text("SELECT COUNT(*) AS total FROM members")
        result = await self.session.execute(stmt)
        row = result.mappings().first()
        return row["total"] if row else 0

    async def get_public_stats(self) -> dict:
        """Count total, active, and alumni members using raw SQL for public statistics."""
        stmt = text(
            """
            SELECT 
                COUNT(*) AS total_members,
                COUNT(*) FILTER (WHERE status = 'Aktif') AS active_members,
                COUNT(*) FILTER (WHERE status = 'Alumni') AS alumni_count
            FROM members
            """
        )
        result = await self.session.execute(stmt)
        row = result.mappings().first()
        return {
            "total_members": row["total_members"] if row else 0,
            "active_members": row["active_members"] if row else 0,
            "alumni_count": row["alumni_count"] if row else 0,
        }

    async def get_public_organization_members(self) -> list[dict]:
        """Return only active, non-sensitive fields for the public organization tree."""
        stmt = text(
            """
            SELECT member_id, full_name, program_of_study, division, role,
                   avatar
            FROM members
            WHERE status = :status AND role <> :member_role
            ORDER BY division NULLS FIRST, role, full_name
            """
        )
        result = await self.session.execute(
            stmt,
            {"status": MemberStatus.AKTIF.value, "member_role": MemberRole.ANGGOTA.value},
        )
        return [dict(row) for row in result.mappings().all()]

    async def create_member(self, member_data: dict, actor: dict | None = None) -> dict:
        """Insert or update member using raw SQL RETURNING * with sanitization and audit logging."""
        # ERP credentials must not be HTML-escaped (the password would be hashed in escaped form)
        create_erp = member_data.pop("create_erp_account", None)
        erp_pwd = member_data.pop("erp_password", None)
        erp_role = member_data.pop("erp_role", None)
        if create_erp and erp_pwd:
            # Fail before writing the member when the actor may not grant this access
            await self._authorize_erp_change(member_data.get("student_id"), actor, erp_role or ERP_ROLE_PENGURUS)

        # Sanitize text fields to prevent injection
        member_data = sanitize_dict_fields(member_data)

        m_id = member_data.get("id", generate_uuid7())
        member_id = member_data.get("member_id")
        if not member_id:
            year = member_id_year(member_data.get("intake_period"), member_data.get("student_id"))
            member_id = await next_member_id(self.session, year)

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

        # Upsert may overwrite an existing member's avatar; remember it to release afterwards
        prev = await self.session.execute(
            text("SELECT avatar FROM members WHERE student_id = :student_id"),
            {"student_id": member_data.get("student_id")},
        )
        previous_avatar = prev.scalar()
        storage = StorageService()
        avatar_value, promoted_avatar = storage.commit_upload_field(
            member_data.get("avatar"), "avatars", keep_values={previous_avatar}, allow_external=True
        )

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
            "avatar": avatar_value,
            "status": stat,
            "join_date": member_data.get("join_date"),
        }
        try:
            result = await self.session.execute(stmt, params)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            storage.unpromote_upload(promoted_avatar)
            raise
        created_row = dict(result.mappings().first())
        if previous_avatar and previous_avatar != avatar_value:
            await release_upload(self.session, previous_avatar)

        # Handle ERP account creation if requested (same authorization rules as the /access endpoint)
        if create_erp and erp_pwd:
            erp_role = erp_role or ERP_ROLE_PENGURUS
            await self.grant_erp_access(created_row["student_id"], password=erp_pwd, erp_role=erp_role, actor=actor)
            created_row["has_erp_access"] = True
            created_row["user_role"] = erp_role
            created_row["user_is_active"] = True

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

        # Extract ERP-specific flags before sanitizing
        create_erp = update_data.pop("create_erp_account", None)
        erp_pwd = update_data.pop("erp_password", None)
        erp_role = update_data.pop("erp_role", None)

        # Managers may not raise their own privileges (role/division drive RBAC) or change their own status
        if actor and not is_superadmin_user(actor) and existing["student_id"] == actor.get("student_id"):
            changed = [f for f in PRIVILEGED_MEMBER_FIELDS if update_data.get(f) is not None]
            if changed:
                raise HTTPException(
                    status_code=403,
                    detail="Akses Ditolak: Anda tidak dapat mengubah jabatan, divisi, atau status keanggotaan Anda sendiri.",
                )
        if create_erp and erp_pwd:
            await self._authorize_erp_change(existing["student_id"], actor, erp_role or ERP_ROLE_PENGURUS)

        update_data = sanitize_dict_fields(update_data)
        fields = []
        params = {"id": existing["id"]}

        storage = StorageService()
        promoted_avatar = None
        if update_data.get("avatar") is not None:
            update_data["avatar"], promoted_avatar = storage.commit_upload_field(
                update_data["avatar"], "avatars", keep_values={existing.get("avatar")}, allow_external=True
            )
            if update_data["avatar"] is None:
                fields.append("avatar = NULL")

        for k, v in update_data.items():
            if k == "division" and v is None:
                fields.append("division = NULL")
                continue
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

        if fields:
            stmt = text(f"UPDATE members SET {', '.join(fields)} WHERE id = :id RETURNING *")  # nosec B608 - column names come from MemberUpdate fields; values are bound
            try:
                result = await self.session.execute(stmt, params)
                await self.session.commit()
            except Exception:
                await self.session.rollback()
                storage.unpromote_upload(promoted_avatar)
                raise
            updated_row = dict(result.mappings().first())
        else:
            updated_row = dict(existing)

        # Replaced avatar: remove the old file unless another record still uses it
        old_avatar = existing.get("avatar")
        if old_avatar and old_avatar != updated_row.get("avatar"):
            await release_upload(self.session, old_avatar)

        # Policy: If status changed to Alumni or Tidak Aktif, automatically revoke/deactivate ERP login access
        new_status = params.get("status")
        if new_status in (MemberStatus.ALUMNI.value, MemberStatus.TIDAK_AKTIF.value):
            await self.session.execute(
                text("UPDATE users SET is_active = false WHERE member_id = :m_id OR student_id = :student_id"),
                {"m_id": existing["id"], "student_id": existing["student_id"]},
            )
            await self.session.commit()
            updated_row["has_erp_access"] = False
            updated_row["user_is_active"] = False

        if new_status == MemberStatus.ALUMNI.value:
            await self.session.execute(
                text(
                    """
                    INSERT INTO alumni_profiles (id, member_id, visibility, consent_given, created_at, updated_at)
                    VALUES (:id, :member_id, false, false, NOW(), NOW())
                    ON CONFLICT (member_id) DO NOTHING
                    """
                ),
                {"id": generate_uuid7(), "member_id": existing["id"]},
            )
            await self.session.commit()

        # If explicit ERP credentials provided in update
        if create_erp and erp_pwd:
            role_val = erp_role or ERP_ROLE_PENGURUS
            await self.grant_erp_access(identifier, password=erp_pwd, erp_role=role_val, actor=actor)
            updated_row["has_erp_access"] = True
            updated_row["user_role"] = role_val
            updated_row["user_is_active"] = True

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

    async def _authorize_erp_change(self, student_id: str | None, actor: dict | None, erp_role: str | None = None) -> None:
        """
        Only a superadmin may grant SUPERADMIN, or change the login account of a superadmin.
        Nobody but a superadmin may change their own ERP account through the member endpoints.
        actor=None is an internal/system call and is allowed.
        """
        if erp_role is not None and erp_role not in ERP_ROLES:
            raise HTTPException(status_code=400, detail=f"Role ERP tidak valid. Pilihan: {', '.join(sorted(ERP_ROLES))}.")
        if actor is None or is_superadmin_user(actor):
            return
        if erp_role == ERP_ROLE_SUPERADMIN:
            raise HTTPException(status_code=403, detail="Akses Ditolak: Hanya Superadmin yang dapat memberikan akses SUPERADMIN.")
        if student_id and student_id == actor.get("student_id"):
            raise HTTPException(status_code=403, detail="Akses Ditolak: Anda tidak dapat mengubah akses ERP akun Anda sendiri.")
        if student_id:
            target = await self.session.execute(
                text("SELECT is_superadmin, role FROM users WHERE student_id = :student_id"),
                {"student_id": student_id},
            )
            row = target.mappings().first()
            if row and (row["is_superadmin"] or (row["role"] or "").upper() == ERP_ROLE_SUPERADMIN):
                raise HTTPException(status_code=403, detail="Akses Ditolak: Akun Superadmin hanya dapat diubah oleh Superadmin.")

    async def grant_erp_access(
        self,
        identifier: str,
        password: str,
        erp_role: str = ERP_ROLE_PENGURUS,
        actor: dict | None = None,
    ) -> dict:
        """Create or activate user account for member to access ERP dashboard."""
        member = await self.get_member_by_identifier(identifier)
        if not member:
            raise HTTPException(status_code=404, detail="Data anggota tidak ditemukan")
        await self._authorize_erp_change(member["student_id"], actor, erp_role)

        hashed_pwd = hash_password(password)
        is_superadmin = erp_role == ERP_ROLE_SUPERADMIN

        user_stmt = text(
            """
            INSERT INTO users (id, member_id, student_id, full_name, email, hashed_password, role, division, is_superadmin, is_active, created_at)
            VALUES (:u_id, :m_id, :student_id, :full_name, :email, :hashed_password, :role, :division, :is_superadmin, true, NOW())
            ON CONFLICT (student_id) DO UPDATE SET
                member_id = EXCLUDED.member_id,
                full_name = EXCLUDED.full_name,
                email = EXCLUDED.email,
                hashed_password = EXCLUDED.hashed_password,
                role = EXCLUDED.role,
                division = EXCLUDED.division,
                is_superadmin = EXCLUDED.is_superadmin,
                is_active = true
            RETURNING id, student_id, full_name, email, role, is_active
            """
        )
        res = await self.session.execute(
            user_stmt,
            {
                "u_id": generate_uuid7(),
                "m_id": member["id"],
                "student_id": member["student_id"],
                "full_name": member["full_name"],
                "email": member["email"],
                "hashed_password": hashed_pwd,
                "role": erp_role,
                "division": member.get("division"),
                "is_superadmin": is_superadmin,
            },
        )
        await self.session.commit()
        user_row = res.mappings().first()

        if actor:
            await log_audit_event(
                session=self.session,
                action="ERP_ACCESS_GRANTED",
                resource_type="USER",
                resource_id=str(user_row["id"]),
                actor_id=actor.get("id"),
                actor_name=actor.get("full_name"),
                actor_role=actor.get("role"),
                details={"student_id": member["student_id"], "erp_role": erp_role},
            )

        return {
            "status": "success",
            "message": f"Akses ERP untuk {member['full_name']} ({member['student_id']}) berhasil diaktifkan.",
            "user": dict(user_row),
        }

    async def revoke_erp_access(self, identifier: str, actor: dict | None = None) -> dict:
        """Deactivate ERP user account for a member (preserves audit log integrity)."""
        member = await self.get_member_by_identifier(identifier)
        if not member:
            raise HTTPException(status_code=404, detail="Data anggota tidak ditemukan")
        await self._authorize_erp_change(member["student_id"], actor)

        stmt = text(
            """
            UPDATE users
            SET is_active = false
            WHERE member_id = :m_id OR student_id = :student_id
            RETURNING id, student_id, full_name, is_active
            """
        )
        res = await self.session.execute(stmt, {"m_id": member["id"], "student_id": member["student_id"]})
        await self.session.commit()
        row = res.mappings().first()

        if not row:
            raise HTTPException(status_code=404, detail="Anggota ini belum memiliki akun akses ERP")

        if actor:
            await log_audit_event(
                session=self.session,
                action="ERP_ACCESS_REVOKED",
                resource_type="USER",
                resource_id=str(row["id"]),
                actor_id=actor.get("id"),
                actor_name=actor.get("full_name"),
                actor_role=actor.get("role"),
                details={"student_id": member["student_id"]},
            )

        return {
            "status": "success",
            "message": f"Akses ERP untuk {member['full_name']} ({member['student_id']}) berhasil dicabut.",
        }

    async def reset_erp_password(self, identifier: str, new_password: str, actor: dict | None = None) -> dict:
        """Reset password for member's ERP user account."""
        member = await self.get_member_by_identifier(identifier)
        if not member:
            raise HTTPException(status_code=404, detail="Data anggota tidak ditemukan")
        await self._authorize_erp_change(member["student_id"], actor)

        hashed_pwd = hash_password(new_password)

        stmt = text(
            """
            UPDATE users
            SET hashed_password = :hashed_pwd, is_active = true
            WHERE member_id = :m_id OR student_id = :student_id
            RETURNING id, student_id, full_name
            """
        )
        res = await self.session.execute(
            stmt,
            {"hashed_pwd": hashed_pwd, "m_id": member["id"], "student_id": member["student_id"]},
        )
        await self.session.commit()
        row = res.mappings().first()

        if not row:
            raise HTTPException(status_code=404, detail="Anggota ini belum memiliki akun akses ERP")

        if actor:
            await log_audit_event(
                session=self.session,
                action="ERP_PASSWORD_RESET",
                resource_type="USER",
                resource_id=str(row["id"]),
                actor_id=actor.get("id"),
                actor_name=actor.get("full_name"),
                actor_role=actor.get("role"),
                details={"student_id": member["student_id"]},
            )

        return {
            "status": "success",
            "message": f"Password ERP untuk {member['full_name']} berhasil diperbarui.",
        }

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
        # Deactivate user login as well
        await self.session.execute(
            text("UPDATE users SET is_active = false WHERE member_id = :m_id OR student_id = :student_id"),
            {"m_id": existing["id"], "student_id": existing["student_id"]},
        )
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

        # Also delete associated user account
        await self.session.execute(
            text("DELETE FROM users WHERE member_id = :id OR student_id = :student_id"),
            {"id": existing["id"], "student_id": existing["student_id"]},
        )
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

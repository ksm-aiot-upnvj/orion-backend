import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from models.enums import Division, MemberRole, MemberStatus, ResearchField, SelectionStatus
from services.audit_log_service import log_audit_event
from services.storage_service import StorageService
from utils.sanitizer import sanitize_dict_fields
from utils.uuid_utils import generate_uuid7


class RegistrationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_registration_by_identifier(self, identifier: str) -> dict | None:
        """Fetch registration by UUID or student_id using raw SQL."""
        try:
            reg_uuid = uuid.UUID(identifier)
            stmt = text("SELECT * FROM registrations WHERE id = :uuid")
            result = await self.session.execute(stmt, {"uuid": reg_uuid})
            return result.mappings().first()
        except ValueError:
            stmt = text("SELECT * FROM registrations WHERE student_id = :identifier")
            result = await self.session.execute(stmt, {"identifier": identifier})
            return result.mappings().first()

    async def create_registration(self, payload: dict, ip_address: str | None = None, user_agent: str | None = None) -> dict:
        """Insert new recruitment candidate with explicit consent and raw SQL."""
        payload = sanitize_dict_fields(payload)

        existing = await self.get_registration_by_identifier(payload["student_id"])
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"NIM {payload['student_id']} sudah terdaftar dalam sistem seleksi!",
            )

        reg_id = payload.get("id", generate_uuid7())
        submit_date = datetime.now().strftime("%d/%m/%Y")
        consent_given = bool(payload.get("consent_given", True))
        consent_timestamp = datetime.now(UTC) if consent_given else None

        # Normalize interest_track to list of string values
        raw_tracks = payload.get("interest_track") or [ResearchField.AI]
        if isinstance(raw_tracks, str):
            raw_tracks = [raw_tracks]
        tracks = [t.value if hasattr(t, "value") else str(t) for t in raw_tracks]

        prodi_val = payload["program_of_study"]
        if hasattr(prodi_val, "value"):
            prodi_val = prodi_val.value

        stmt = text(
            """
            INSERT INTO registrations (
                id, student_id, full_name, program_of_study, email, contact_info,
                intake_period, interest_track, motivation, photo, status, submit_date,
                consent_given, consent_timestamp, created_at, updated_at
            )
            VALUES (
                :id, :student_id, :full_name, :program_of_study, :email, :contact_info,
                :intake_period, :interest_track, :motivation, :photo, :status, :submit_date,
                :consent_given, :consent_timestamp, NOW(), NOW()
            )
            RETURNING *
            """
        )
        params = {
            "id": reg_id,
            "student_id": payload["student_id"],
            "full_name": payload["full_name"],
            "program_of_study": prodi_val,
            "email": payload["email"],
            "contact_info": payload.get("contact_info"),
            "intake_period": payload["intake_period"],
            "interest_track": tracks,
            "motivation": payload.get("motivation"),
            "photo": payload.get("photo"),
            "status": SelectionStatus.PENDING.value,
            "submit_date": submit_date,
            "consent_given": consent_given,
            "consent_timestamp": consent_timestamp,
        }
        result = await self.session.execute(stmt, params)
        await self.session.commit()
        created_reg = result.mappings().first()

        # Audit Log: Public registration event
        await log_audit_event(
            session=self.session,
            action="REGISTRATION_SUBMITTED",
            resource_type="REGISTRATION",
            resource_id=str(reg_id),
            actor_id=None,
            actor_name=payload["full_name"],
            actor_role="CANDIDATE",
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "student_id": payload["student_id"],
                "prodi": prodi_val,
                "consent_given": consent_given,
            },
        )

        return created_reg

    async def get_all_registrations(self, status_filter: str | None = None) -> list[dict]:
        """Fetch all registrations using raw SQL."""
        query_str = """
            SELECT id, student_id, full_name, program_of_study, email, contact_info,
                   intake_period, interest_track, motivation, photo, status, member_id,
                   review_note, submit_date, consent_given, consent_timestamp, created_at, updated_at
            FROM registrations
            WHERE 1=1
        """
        params = {}
        if status_filter and status_filter.lower() != "all":
            s_lower = status_filter.lower()
            if s_lower in ("approved", "accepted"):
                normalized_status = SelectionStatus.ACCEPTED.value
            elif s_lower == "rejected":
                normalized_status = SelectionStatus.REJECTED.value
            else:
                normalized_status = SelectionStatus.PENDING.value

            query_str += " AND status = :status"
            params["status"] = normalized_status

        query_str += " ORDER BY created_at DESC"
        result = await self.session.execute(text(query_str), params)
        return result.mappings().all()

    async def approve_registration(
        self,
        identifier: str,
        reviewer_name: str,
        reviewer_role: str,
        reviewer_id: uuid.UUID | str | None = None,
        division: str | Division | None = None,
        role: str | MemberRole | None = MemberRole.ANGGOTA,
    ) -> dict:
        """Approve candidate, generate member ID and insert to members table using raw SQL."""
        reg = await self.get_registration_by_identifier(identifier)
        if not reg:
            raise HTTPException(status_code=404, detail="Data pendaftar tidak ditemukan")

        if reg["status"] == SelectionStatus.ACCEPTED.value and reg.get("member_id"):
            return reg

        # Count members for sequential ID
        count_stmt = text("SELECT COUNT(*) AS total FROM members")
        count_res = await self.session.execute(count_stmt)
        total_members = count_res.mappings().first()["total"]

        intake_raw = str(reg.get("intake_period") or "").strip()
        student_id_raw = str(reg.get("student_id") or "").strip()
        if intake_raw.isdigit() and len(intake_raw) == 4:
            year = intake_raw
        elif intake_raw.isdigit() and len(intake_raw) == 2:
            year = f"20{intake_raw}"
        elif len(student_id_raw) >= 2 and student_id_raw[:2].isdigit():
            year = f"20{student_id_raw[:2]}"
        else:
            year = str(datetime.now().year)

        member_id = f"AIOT-{year}-{str(total_members + 1).zfill(3)}"
        review_note = f"Disetujui oleh {reviewer_name} ({reviewer_role})"

        # Update registration status
        update_stmt = text(
            """
            UPDATE registrations
            SET status = :status, member_id = :member_id, review_note = :review_note, updated_at = NOW()
            WHERE id = :id
            RETURNING *
            """
        )
        updated_res = await self.session.execute(
            update_stmt,
            {
                "status": SelectionStatus.ACCEPTED.value,
                "member_id": member_id,
                "review_note": review_note,
                "id": reg["id"],
            },
        )
        updated_reg = updated_res.mappings().first()

        # Check existing member
        check_member = text("SELECT id FROM members WHERE student_id = :student_id")
        existing_m = await self.session.execute(check_member, {"student_id": reg["student_id"]})
        if not existing_m.mappings().first():
            reg_tracks = reg.get("interest_track") or []
            if isinstance(reg_tracks, str):
                reg_tracks = [reg_tracks]

            div_val = division.value if hasattr(division, "value") else division
            role_val = role.value if hasattr(role, "value") else (role or MemberRole.ANGGOTA.value)

            insert_m_stmt = text(
                """
                INSERT INTO members (id, member_id, student_id, full_name, program_of_study, email, contact_info, division, role, intake_period, interest_track, avatar, status, join_date, created_at)
                VALUES (:id, :member_id, :student_id, :full_name, :program_of_study, :email, :contact_info, :division, :role, :intake_period, :interest_track, :avatar, :status, :join_date, NOW())
                """
            )
            await self.session.execute(
                insert_m_stmt,
                {
                    "id": generate_uuid7(),
                    "member_id": member_id,
                    "student_id": reg["student_id"],
                    "full_name": reg["full_name"],
                    "program_of_study": reg["program_of_study"],
                    "email": reg["email"],
                    "contact_info": reg.get("contact_info"),
                    "division": div_val,
                    "role": role_val,
                    "intake_period": reg["intake_period"],
                    "interest_track": reg_tracks,
                    "avatar": reg.get("photo"),
                    "status": MemberStatus.AKTIF.value,
                    "join_date": datetime.now().strftime("%d/%m/%Y"),
                },
            )

        await self.session.commit()

        # Audit log
        await log_audit_event(
            session=self.session,
            action="REGISTRATION_APPROVED",
            resource_type="REGISTRATION",
            resource_id=str(reg["id"]),
            actor_id=reviewer_id,
            actor_name=reviewer_name,
            actor_role=reviewer_role,
            details={"member_id": member_id, "student_id": reg["student_id"]},
        )

        return updated_reg

    async def reject_registration(
        self,
        identifier: str,
        reviewer_name: str,
        reviewer_role: str,
        reviewer_id: uuid.UUID | str | None = None,
    ) -> dict:
        """Reject candidate application using raw SQL."""
        reg = await self.get_registration_by_identifier(identifier)
        if not reg:
            raise HTTPException(status_code=404, detail="Data pendaftar tidak ditemukan")

        review_note = f"Ditolak oleh {reviewer_name} ({reviewer_role})"
        stmt = text(
            """
            UPDATE registrations
            SET status = :status, review_note = :review_note, updated_at = NOW()
            WHERE id = :id
            RETURNING *
            """
        )
        res = await self.session.execute(
            stmt,
            {
                "status": SelectionStatus.REJECTED.value,
                "review_note": review_note,
                "id": reg["id"],
            },
        )
        await self.session.commit()
        rejected_reg = res.mappings().first()

        # Audit log
        await log_audit_event(
            session=self.session,
            action="REGISTRATION_REJECTED",
            resource_type="REGISTRATION",
            resource_id=str(reg["id"]),
            actor_id=reviewer_id,
            actor_name=reviewer_name,
            actor_role=reviewer_role,
            details={"student_id": reg["student_id"]},
        )

        return rejected_reg

    async def delete_registration(self, identifier: str, actor: dict | None = None) -> bool:
        """Hard delete registration and unlink physical photo (Right to Erasure)."""
        reg = await self.get_registration_by_identifier(identifier)
        if not reg:
            return False

        # Unlink physical photo file if stored locally
        if reg.get("photo"):
            StorageService().delete_avatar(reg["photo"])

        stmt = text("DELETE FROM registrations WHERE id = :id")
        await self.session.execute(stmt, {"id": reg["id"]})
        await self.session.commit()

        if actor:
            await log_audit_event(
                session=self.session,
                action="REGISTRATION_DELETED",
                resource_type="REGISTRATION",
                resource_id=str(reg["id"]),
                actor_id=actor.get("id"),
                actor_name=actor.get("full_name"),
                actor_role=actor.get("role"),
                details={"student_id": reg["student_id"]},
            )

        return True

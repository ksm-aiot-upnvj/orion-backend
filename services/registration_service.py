import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def create_registration(self, payload: dict) -> dict:
        """Insert new recruitment candidate using raw SQL."""
        existing = await self.get_registration_by_identifier(payload["student_id"])
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"NIM {payload['student_id']} sudah terdaftar dalam sistem seleksi!"
            )

        reg_id = payload.get("id", generate_uuid7())
        submit_date = datetime.now().strftime("%d/%m/%Y")

        stmt = text(
            """
            INSERT INTO registrations (
                id, student_id, full_name, program_of_study, email, contact_info,
                intake_period, interest_track, motivation, photo, status, submit_date,
                created_at, updated_at
            )
            VALUES (
                :id, :student_id, :full_name, :program_of_study, :email, :contact_info,
                :intake_period, :interest_track, :motivation, :photo, 'PENDING', :submit_date,
                NOW(), NOW()
            )
            RETURNING *
            """
        )
        params = {
            "id": reg_id,
            "student_id": payload["student_id"],
            "full_name": payload["full_name"],
            "program_of_study": payload["program_of_study"],
            "email": payload["email"],
            "contact_info": payload.get("contact_info"),
            "intake_period": payload["intake_period"],
            "interest_track": payload["interest_track"],
            "motivation": payload.get("motivation"),
            "photo": payload.get("photo"),
            "submit_date": submit_date
        }
        result = await self.session.execute(stmt, params)
        await self.session.commit()
        return result.mappings().first()

    async def get_all_registrations(self, status_filter: str | None = None) -> list[dict]:
        """Fetch all registrations using raw SQL."""
        query_str = """
            SELECT id, student_id, full_name, program_of_study, email, contact_info, intake_period, interest_track, motivation, photo, status, member_id, review_note, submit_date, created_at, updated_at
            FROM registrations
            WHERE 1=1
        """
        params = {}
        if status_filter and status_filter != "all":
            query_str += " AND status = :status"
            params["status"] = status_filter

        query_str += " ORDER BY created_at DESC"
        result = await self.session.execute(text(query_str), params)
        return result.mappings().all()

    async def approve_registration(self, identifier: str, reviewer_name: str, reviewer_role: str) -> dict:
        """Approve candidate, generate member ID and insert to members table using raw SQL."""
        reg = await self.get_registration_by_identifier(identifier)
        if not reg:
            raise HTTPException(status_code=404, detail="Data pendaftar tidak ditemukan")

        if reg["status"] == "APPROVED" and reg.get("member_id"):
            return reg

        # Count members for sequential ID
        count_stmt = text("SELECT COUNT(*) AS total FROM members")
        count_res = await self.session.execute(count_stmt)
        total_members = count_res.mappings().first()["total"]
        member_id = f"AIOT-2026-{str(total_members + 1).zfill(3)}"
        review_note = f"Disetujui oleh {reviewer_name} ({reviewer_role})"

        # Update registration status
        update_stmt = text(
            """
            UPDATE registrations
            SET status = 'APPROVED', member_id = :member_id, review_note = :review_note, updated_at = NOW()
            WHERE id = :id
            RETURNING *
            """
        )
        updated_res = await self.session.execute(update_stmt, {
            "member_id": member_id,
            "review_note": review_note,
            "id": reg["id"]
        })
        updated_reg = updated_res.mappings().first()

        # Check existing member
        check_member = text("SELECT id FROM members WHERE student_id = :student_id")
        existing_m = await self.session.execute(check_member, {"student_id": reg["student_id"]})
        if not existing_m.mappings().first():
            division = "Akademik & Riset" if "Artificial" in reg["interest_track"] or "Robotics" in reg["interest_track"] else "Pengembangan SDM"
            insert_m_stmt = text(
                """
                INSERT INTO members (id, member_id, student_id, full_name, program_of_study, email, contact_info, division, role, intake_period, interest_track, avatar, status, join_date, created_at)
                VALUES (:id, :member_id, :student_id, :full_name, :program_of_study, :email, :contact_info, :division, :role, :intake_period, :interest_track, :avatar, 'Aktif (Anggota Baru)', :join_date, NOW())
                """
            )
            await self.session.execute(insert_m_stmt, {
                "id": generate_uuid7(),
                "member_id": member_id,
                "student_id": reg["student_id"],
                "full_name": reg["full_name"],
                "program_of_study": reg["program_of_study"],
                "email": reg["email"],
                "contact_info": reg.get("contact_info"),
                "division": division,
                "role": f"Staff {reg['interest_track'].split('&')[0].strip()}",
                "intake_period": reg["intake_period"],
                "interest_track": reg["interest_track"],
                "avatar": reg.get("photo"),
                "join_date": datetime.now().strftime("%d/%m/%Y")
            })

        await self.session.commit()
        return updated_reg

    async def reject_registration(self, identifier: str, reviewer_name: str, reviewer_role: str) -> dict:
        """Reject candidate application using raw SQL."""
        reg = await self.get_registration_by_identifier(identifier)
        if not reg:
            raise HTTPException(status_code=404, detail="Data pendaftar tidak ditemukan")

        review_note = f"Ditolak oleh {reviewer_name} ({reviewer_role})"
        stmt = text(
            """
            UPDATE registrations
            SET status = 'REJECTED', review_note = :review_note, updated_at = NOW()
            WHERE id = :id
            RETURNING *
            """
        )
        res = await self.session.execute(stmt, {"review_note": review_note, "id": reg["id"]})
        await self.session.commit()
        return res.mappings().first()

import re
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def member_id_year(intake_period: str | None, student_id: str | None) -> str:
    """Year part of a member ID: intake year (4 or 2 digits), else NIM prefix, else the current year."""
    intake_raw = str(intake_period or "").strip()
    student_id_raw = str(student_id or "").strip()
    if intake_raw.isdigit() and len(intake_raw) == 4:
        return intake_raw
    if intake_raw.isdigit() and len(intake_raw) == 2:
        return f"20{intake_raw}"
    if len(student_id_raw) >= 2 and student_id_raw[:2].isdigit():
        return f"20{student_id_raw[:2]}"
    return str(datetime.now().year)


async def next_member_id(session: AsyncSession, year: str) -> str:
    """Allocate the next permanent AIOT ID for a year, atomically and without reusing deleted IDs."""
    result = await session.execute(
        text(
            """
            INSERT INTO member_id_counters (intake_year, last_issued)
            VALUES (:year, 1)
            ON CONFLICT (intake_year) DO UPDATE
            SET last_issued = member_id_counters.last_issued + 1
            RETURNING last_issued
            """
        ),
        {"year": year},
    )
    number = result.scalar_one()
    return f"AIOT-{year}-{str(number).zfill(3)}"


async def reserve_member_id(session: AsyncSession, member_id: str | None) -> None:
    """Advance the permanent counter when a caller supplies a standard AIOT ID explicitly."""
    match = re.fullmatch(r"AIOT-(\d{4})-(\d+)", str(member_id or ""))
    if not match:
        return

    year, number = match.groups()
    await session.execute(
        text(
            """
            INSERT INTO member_id_counters (intake_year, last_issued)
            VALUES (:year, :number)
            ON CONFLICT (intake_year) DO UPDATE
            SET last_issued = GREATEST(member_id_counters.last_issued, EXCLUDED.last_issued)
            """
        ),
        {"year": year, "number": int(number)},
    )

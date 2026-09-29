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
    """Next free AIOT-<year>-NNN: highest existing number for that year + 1 (a COUNT would reuse deleted IDs)."""
    result = await session.execute(
        text("SELECT member_id FROM members WHERE member_id LIKE :prefix"), {"prefix": f"AIOT-{year}-%"}
    )
    max_num = 0
    for member_id in result.scalars().all():
        try:
            max_num = max(max_num, int(str(member_id).split("-")[-1]))
        except ValueError:
            continue
    return f"AIOT-{year}-{str(max_num + 1).zfill(3)}"

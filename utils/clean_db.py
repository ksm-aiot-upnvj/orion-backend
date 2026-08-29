import asyncio
from config.db import AsyncSessionLocal
from sqlalchemy import text

# The 11 dummy student_ids that were seeded prior to the official Excel ingestion
DUMMY_STUDENT_IDS = [
    "2310511001",
    "2310511002",
    "2310511015",
    "2310511022",
    "2310511030",
    "2410511012",
    "2410511018",
    "2310511041",
    "2410511050",
    "2310511062",
    "2410511077",
]

async def clean():
    async with AsyncSessionLocal() as session:
        # Check if any dummy student IDs are present
        stmt_del_members = text("DELETE FROM members WHERE student_id = ANY(:ids)")
        res1 = await session.execute(stmt_del_members, {"ids": DUMMY_STUDENT_IDS})
        print(f"Deleted {res1.rowcount} dummy members from members table.")

        stmt_del_users = text("DELETE FROM users WHERE student_id = ANY(:ids)")
        res2 = await session.execute(stmt_del_users, {"ids": DUMMY_STUDENT_IDS})
        print(f"Deleted {res2.rowcount} dummy users from users table.")

        # Re-number member_id sequentially AIOT-2026-001 ... AIOT-2026-035
        all_members = await session.execute(text("SELECT id, student_id, full_name, role FROM members ORDER BY created_at ASC, student_id ASC"))
        members_list = all_members.mappings().all()
        print(f"Remaining authentic members: {len(members_list)}")

        for idx, m in enumerate(members_list, start=1):
            seq_id = f"AIOT-2026-{str(idx).zfill(3)}"
            await session.execute(
                text("UPDATE members SET member_id = :member_id WHERE id = :id"),
                {"member_id": seq_id, "id": m["id"]}
            )
            print(f"  [{seq_id}] {m['student_id']} - {m['full_name']} ({m['role']})")

        await session.commit()
        print("Database cleanup & sync complete!")

if __name__ == "__main__":
    asyncio.run(clean())

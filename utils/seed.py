import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config.db import AsyncSessionLocal
from models.enums import Division
from utils.security import hash_password
from utils.uuid_utils import generate_uuid7

SUPERADMIN_STUDENT_ID = "2210511084"
SUPERADMIN_NAME = "Dzulfikri Adjmal"
SUPERADMIN_EMAIL = "2210511084@mahasiswa.upnvj.ac.id"
SUPERADMIN_PASSWORD = "OrionAdmin#2026!"


async def seed_superadmin(db: AsyncSession) -> dict:
    """Seed or update Superadmin account."""
    hashed_pwd = hash_password(SUPERADMIN_PASSWORD)

    stmt = text(
        """
        INSERT INTO users (id, student_id, full_name, email, hashed_password, role, division, avatar, is_active, created_at)
        VALUES (:id, :student_id, :full_name, :email, :hashed_password, 'SUPERADMIN', :division, NULL, true, NOW())
        ON CONFLICT (student_id) DO UPDATE SET
            full_name = EXCLUDED.full_name,
            email = EXCLUDED.email,
            hashed_password = EXCLUDED.hashed_password,
            role = 'SUPERADMIN',
            division = EXCLUDED.division,
            is_active = true
        RETURNING id, student_id, full_name, email, role, division, is_active;
        """
    )
    result = await db.execute(stmt, {
        "id": generate_uuid7(),
        "student_id": SUPERADMIN_STUDENT_ID,
        "full_name": SUPERADMIN_NAME,
        "email": SUPERADMIN_EMAIL,
        "hashed_password": hashed_pwd,
        "division": Division.BPH.value,
    })
    await db.commit()
    return result.mappings().first()


async def seed_database(db: AsyncSession):
    """Main database seeder function."""
    await seed_superadmin(db)


async def main():
    async with AsyncSessionLocal() as session:
        user = await seed_superadmin(session)
        print("Superadmin successfully seeded!")
        print(f"NIM      : {user['student_id']}")
        print(f"Nama     : {user['full_name']}")
        print(f"Email    : {user['email']}")
        print(f"Role     : {user['role']}")
        print(f"Divisi   : {user['division']}")
        print(f"Password : {SUPERADMIN_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())



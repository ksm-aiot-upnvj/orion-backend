import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config.config import settings
from config.db import AsyncSessionLocal
from models.enums import Division
from utils.security import hash_password
from utils.uuid_utils import generate_uuid7


async def seed_superadmin(db: AsyncSession) -> dict:
    """Seed or update Superadmin account."""
    hashed_pwd = hash_password(settings.SUPERADMIN_PW)

    stmt = text(
        """
        INSERT INTO users (id, student_id, full_name, email, hashed_password, role, division, avatar, is_superadmin, is_active, created_at)
        VALUES (:id, :student_id, :full_name, :email, :hashed_password, 'SUPERADMIN', :division, NULL, true, true, NOW())
        ON CONFLICT (student_id) DO UPDATE SET
            full_name = EXCLUDED.full_name,
            email = EXCLUDED.email,
            hashed_password = EXCLUDED.hashed_password,
            role = 'SUPERADMIN',
            division = EXCLUDED.division,
            is_superadmin = true,
            is_active = true
        RETURNING id, student_id, full_name, email, role, division, is_superadmin, is_active;
        """
    )
    result = await db.execute(stmt, {
        "id": generate_uuid7(),
        "student_id": settings.SUPERADMIN_NIM,
        "full_name": settings.SUPERADMIN_NAME,
        "email": settings.SUPERADMIN_EMAIL,
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
        print("Password : (dari SUPERADMIN_PW di .env)")


if __name__ == "__main__":
    asyncio.run(main())



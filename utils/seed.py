from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from utils.uuid_utils import generate_uuid7


async def seed_registrations(db: AsyncSession):
    """Seed initial recruitment candidate submissions for selection pipeline."""
    # Check if table already has records
    check_stmt = text("SELECT COUNT(*) AS total FROM registrations")
    res = await db.execute(check_stmt)
    if res.mappings().first()["total"] > 0:
        return

    registrations_data = [
        {
            "id": generate_uuid7(),
            "student_id": "2510511090",
            "full_name": "Satria Bagus Prakoso",
            "program_of_study": "S1 Informatika",
            "email": "satria.bagus@mahasiswa.upnvj.ac.id",
            "phone_number": "081299887766",
            "interest_track": "Artificial Intelligence / Machine Learning",
            "motivation": "Tertarik mendalami Computer Vision dan Edge AI untuk smart robotics di KSM AIoT.",
            "status": "PENDING",
            "member_id": None
        },
        {
            "id": generate_uuid7(),
            "student_id": "2510511095",
            "full_name": "Clarissa Aurelia",
            "program_of_study": "S1 Sistem Informasi",
            "email": "clarissa.aurelia@mahasiswa.upnvj.ac.id",
            "phone_number": "081377889900",
            "interest_track": "Internet of Things (IoT)",
            "motivation": "Ingin berkontribusi dalam riset smart agriculture dan sensor telemetry berbasis ESP32.",
            "status": "PENDING",
            "member_id": None
        },
        {
            "id": generate_uuid7(),
            "student_id": "2510511099",
            "full_name": "Daffa Ramadhan",
            "program_of_study": "S1 Informatika",
            "email": "daffa.ramadhan@mahasiswa.upnvj.ac.id",
            "phone_number": "082144556677",
            "interest_track": "Software Backend",
            "motivation": "Sangat antusias membangun microservices backend performa tinggi dengan FastAPI dan Docker.",
            "status": "PENDING",
            "member_id": None
        }
    ]

    for reg in registrations_data:
        insert_stmt = text(
            """
            INSERT INTO registrations (id, student_id, full_name, program_of_study, email, phone_number, interest_track, motivation, status, member_id, created_at)
            VALUES (:id, :student_id, :full_name, :program_of_study, :email, :phone_number, :interest_track, :motivation, :status, :member_id, NOW())
            ON CONFLICT (student_id) DO NOTHING
            """
        )
        await db.execute(insert_stmt, reg)

    await db.commit()


async def seed_database(db: AsyncSession):
    """Main database seeder function."""
    await seed_registrations(db)

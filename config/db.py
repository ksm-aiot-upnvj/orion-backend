import os
from collections.abc import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from config.config import settings

NAMING = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)
Base = declarative_base(metadata=NAMING)

db_url = settings.get_database_url()

is_testing = bool(os.getenv("PYTEST_CURRENT_TEST")) or settings.ENVIRONMENT == "test"

engine_kwargs = {"echo": False}
if is_testing:
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
    })

engine = create_async_engine(db_url, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency for obtaining async SQLAlchemy session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


ENUM_DEFINITIONS_SQL = """
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'selection_status_enum') THEN
        CREATE TYPE selection_status_enum AS ENUM ('Accepted', 'Pending', 'Rejected');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'member_status_enum') THEN
        CREATE TYPE member_status_enum AS ENUM ('Aktif', 'Tidak Aktif', 'Alumni');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'research_field_enum') THEN
        CREATE TYPE research_field_enum AS ENUM ('IoT Embedded', 'AI', 'Software Engineer & Cloud');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'role_enum') THEN
        CREATE TYPE role_enum AS ENUM ('Ketua', 'Wakil Ketua', 'Sekretaris', 'Bendahara', 'Kepala Divisi', 'Staff', 'Anggota');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'division_enum') THEN
        CREATE TYPE division_enum AS ENUM ('BPH', 'Akademik Riset', 'PSDM', 'Humas Multimedia');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'study_program_enum') THEN
        CREATE TYPE study_program_enum AS ENUM ('S1 Informatika', 'S1 Sistem Informasi', 'S1 Sains Data', 'D3 Sistem Informasi');
    END IF;
END $$;
"""


async def ensure_enums_and_tables(connection):
    """Ensure all PostgreSQL custom ENUM types and tables exist (safe on fresh & existing DB)."""
    from sqlalchemy import text
    await connection.execute(text(ENUM_DEFINITIONS_SQL))
    await connection.run_sync(Base.metadata.create_all)


from sqlalchemy.ext.asyncio import AsyncSession


async def seed_registrations(db: AsyncSession):
    """Clean registration pipeline - no fake mock data inserted."""
    pass


async def seed_database(db: AsyncSession):
    """Main database seeder function."""
    await seed_registrations(db)


from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from config.db import AsyncSessionLocal


async def get_session() -> AsyncGenerator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

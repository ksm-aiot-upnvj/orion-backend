import pytest
from sqlalchemy import text

from config.db import AsyncSessionLocal
from utils.rate_limiter import InMemoryRateLimiter


@pytest.fixture(autouse=True)
async def auto_clean_database_noise():
    """
    Automatic fixture executed for each test function to guarantee
    zero test noise / garbage accumulation in the PostgreSQL database.
    """
    InMemoryRateLimiter.reset()
    yield
    InMemoryRateLimiter.reset()

    # Teardown: Clean up any test records created during test execution
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("DELETE FROM registrations WHERE full_name LIKE '%Consent Test%' OR full_name LIKE '%Exceeded%' OR email LIKE '%consent_%@upnvj.ac.id'")
            )
            await session.execute(
                text("DELETE FROM audit_logs WHERE resource_type = 'SECURITY_TEST' OR action LIKE '%TEST%'")
            )
            await session.execute(
                text("DELETE FROM members WHERE student_id = '2410511999' OR email LIKE '%test_rbac%'")
            )
            # Restore intake config if modified during tests
            await session.execute(
                text("""
                    UPDATE system_settings
                    SET value = '{"status": "OPEN", "batch_name": "Penerimaan Anggota Baru Periode 2026", "deadline": "2026-12-31", "quota": 100}',
                        updated_at = NOW()
                    WHERE key = 'intake_config';
                """)
            )
            await session.commit()
    except Exception as e:
        print(f"Warning: Teardown cleanup encountered an error: {e}")

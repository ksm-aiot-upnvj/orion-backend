"""Regression test: a failed audit write must not poison the request's DB session."""

import pytest
from sqlalchemy import text

from config.db import AsyncSessionLocal, engine
from services.audit_log_service import log_audit_event


@pytest.fixture(autouse=True)
async def cleanup():
    yield
    await engine.dispose()


@pytest.mark.asyncio
async def test_session_usable_after_failed_audit_write():
    async with AsyncSessionLocal() as session:
        # resource_type is VARCHAR(50): the insert fails inside the DB
        result = await log_audit_event(session, action="SECURITY_TEST", resource_type="X" * 80)
        assert result is None
        assert (await session.execute(text("SELECT 1"))).scalar() == 1

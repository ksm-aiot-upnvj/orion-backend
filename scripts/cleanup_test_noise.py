import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from config.db import AsyncSessionLocal

async def cleanup():
    async with AsyncSessionLocal() as session:
        # 1. Clean test registrations
        del_reg = await session.execute(
            text("DELETE FROM registrations WHERE full_name LIKE '%Consent Test%' OR full_name LIKE '%Exceeded%' OR student_id LIKE '24%' AND email LIKE '%test%' RETURNING student_id")
        )
        deleted_regs = del_reg.fetchall()
        print(f"Deleted {len(deleted_regs)} test registration records.")

        # 2. Clean test audit logs
        del_audit = await session.execute(
            text("DELETE FROM audit_logs WHERE resource_type = 'SECURITY_TEST' OR action LIKE '%TEST%' RETURNING id")
        )
        deleted_audits = del_audit.fetchall()
        print(f"Deleted {len(deleted_audits)} test audit log records.")

        # 3. Clean test members if any
        del_members = await session.execute(
            text("DELETE FROM members WHERE student_id = '2410511999' OR email LIKE '%test_rbac%' RETURNING id")
        )
        deleted_members = del_members.fetchall()
        print(f"Deleted {len(deleted_members)} test member records.")

        # 4. Reset intake_config to standard default
        reset_intake = await session.execute(
            text("""
                UPDATE system_settings
                SET value = '{"status": "OPEN", "batch_name": "Penerimaan Anggota Baru Periode 2026", "deadline": "2026-08-31", "quota": 100}',
                    updated_at = NOW()
                WHERE key = 'intake_config'
                RETURNING key, value;
            """)
        )
        reset_row = reset_intake.mappings().first()
        if reset_row:
            print(f"Reset intake_config: {reset_row['value']}")

        await session.commit()
        print("Database cleanup completed successfully.")

if __name__ == "__main__":
    asyncio.run(cleanup())

"""Add permanent per-year member ID counters.

Revision ID: a19e7c4d2b60
Revises: 4f8b9e1c2a3d
Create Date: 2026-09-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a19e7c4d2b60"
down_revision: str | Sequence[str] | None = "4f8b9e1c2a3d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "member_id_counters",
        sa.Column("intake_year", sa.String(length=4), nullable=False),
        sa.Column("last_issued", sa.Integer(), nullable=False),
        sa.CheckConstraint("last_issued >= 0", name="ck_member_id_counters_last_issued_nonnegative"),
        sa.PrimaryKeyConstraint("intake_year", name="pk_member_id_counters"),
    )

    # Include accepted registrations too, because their member may have been deleted.
    op.execute(
        sa.text(
            """
            INSERT INTO member_id_counters (intake_year, last_issued)
            SELECT intake_year, MAX(sequence_number)
            FROM (
                SELECT substring(member_id from '^AIOT-([0-9]{4})-') AS intake_year,
                       substring(member_id from '-([0-9]+)$')::integer AS sequence_number
                FROM members
                WHERE member_id ~ '^AIOT-[0-9]{4}-[0-9]+$'
                UNION ALL
                SELECT substring(member_id from '^AIOT-([0-9]{4})-') AS intake_year,
                       substring(member_id from '-([0-9]+)$')::integer AS sequence_number
                FROM registrations
                WHERE member_id ~ '^AIOT-[0-9]{4}-[0-9]+$'
            ) assigned_ids
            GROUP BY intake_year
            """
        )
    )


def downgrade() -> None:
    op.drop_table("member_id_counters")

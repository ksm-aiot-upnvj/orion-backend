"""add alumni profiles

Revision ID: 3d1c8f6a2b7e
Revises: 207a6cc09ec3
Create Date: 2026-09-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3d1c8f6a2b7e"
down_revision: str | Sequence[str] | None = "207a6cc09ec3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "alumni_profiles" not in inspector.get_table_names():
        op.create_table(
            "alumni_profiles",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("member_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("graduation_year", sa.String(length=4), nullable=True),
            sa.Column("current_company", sa.String(length=150), nullable=True),
            sa.Column("current_role", sa.String(length=150), nullable=True),
            sa.Column("linkedin_url", sa.Text(), nullable=True),
            sa.Column("testimonial", sa.Text(), nullable=True),
            sa.Column("visibility", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("consent_given", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("member_id"),
        )

    existing_indexes = {index["name"] for index in inspector.get_indexes("alumni_profiles")}
    if "ix_alumni_profiles_member_id" not in existing_indexes:
        op.create_index("ix_alumni_profiles_member_id", "alumni_profiles", ["member_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_alumni_profiles_member_id", table_name="alumni_profiles")
    op.drop_table("alumni_profiles")

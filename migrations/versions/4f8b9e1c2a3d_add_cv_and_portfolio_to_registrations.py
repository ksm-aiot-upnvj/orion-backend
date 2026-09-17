"""add cv and portfolio to registrations

Revision ID: 4f8b9e1c2a3d
Revises: 3d1c8f6a2b7e
Create Date: 2026-09-17 21:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4f8b9e1c2a3d"
down_revision: str | Sequence[str] | None = "3d1c8f6a2b7e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = [c["name"] for c in inspector.get_columns("registrations")]
    if "cv_url" not in columns:
        op.add_column("registrations", sa.Column("cv_url", sa.String(length=255), nullable=True))
    if "portfolio_url" not in columns:
        op.add_column("registrations", sa.Column("portfolio_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = [c["name"] for c in inspector.get_columns("registrations")]
    if "portfolio_url" in columns:
        op.drop_column("registrations", "portfolio_url")
    if "cv_url" in columns:
        op.drop_column("registrations", "cv_url")

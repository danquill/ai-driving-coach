"""Add lap_number to coaching_insights.

Revision ID: 007
Revises: 006
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "coaching_insights",
        sa.Column("lap_number", sa.SmallInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("coaching_insights", "lap_number")

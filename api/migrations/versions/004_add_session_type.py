"""Add session_type column to sessions table.

Revision ID: 004
Revises: 003
Create Date: 2026-04-05 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision: str = "004"
down_revision: str = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE sessions
        ADD COLUMN IF NOT EXISTS session_type TEXT
        CHECK (session_type IN ('hpde', 'practice', 'qualifying', 'race', 'test'))
        DEFAULT 'hpde'
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE sessions DROP COLUMN IF EXISTS session_type")

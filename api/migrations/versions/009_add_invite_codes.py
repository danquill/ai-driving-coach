"""Add invite_codes table for beta registration gating.

Revision ID: 009
Revises: 008
Create Date: 2026-04-11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE invite_codes (
            id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            code        TEXT UNIQUE NOT NULL,
            email       TEXT,
            used_at     TIMESTAMPTZ,
            used_by     UUID REFERENCES users(id) ON DELETE SET NULL,
            created_by  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX idx_invite_codes_code ON invite_codes(code)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS invite_codes")

"""Add events table and event_id FK on sessions.

Revision ID: 008
Revises: 007
Create Date: 2026-04-11
"""

from __future__ import annotations

from alembic import op

revision: str = "008"
down_revision: str = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            owner_id   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            circuit_id UUID REFERENCES circuits(id) ON DELETE SET NULL,
            name       TEXT NOT NULL,
            event_date DATE,
            notes      TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_owner ON events(owner_id)")

    op.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS event_id UUID REFERENCES events(id) ON DELETE SET NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sessions_event ON sessions(event_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_sessions_event")
    op.execute("ALTER TABLE sessions DROP COLUMN IF EXISTS event_id")
    op.execute("DROP TABLE IF EXISTS events CASCADE")

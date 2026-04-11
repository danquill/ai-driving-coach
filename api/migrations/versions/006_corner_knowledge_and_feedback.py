"""Add circuit_corner_knowledge table and feedback columns to coaching_insights.

Revision ID: 006
Revises: 005
Create Date: 2026-04-09 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision: str = "006"
down_revision: str = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS circuit_corner_knowledge (
            id                        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            circuit_id                UUID NOT NULL REFERENCES circuits(id) ON DELETE CASCADE,
            corner_number             SMALLINT,
            typical_phase_of_interest TEXT CHECK (
                typical_phase_of_interest IN ('entry', 'turn-in', 'mid-corner', 'exit')
            ),
            known_handling_tendency   TEXT,
            correct_technique         TEXT,
            incorrect_recommendations JSONB,
            coaching_notes            TEXT,
            source                    TEXT NOT NULL DEFAULT 'manual'
                                      CHECK (source IN ('manual', 'correction')),
            created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at                TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ccknowledge_circuit_id "
        "ON circuit_corner_knowledge(circuit_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ccknowledge_circuit_corner "
        "ON circuit_corner_knowledge(circuit_id, corner_number)"
    )
    op.execute("""
        ALTER TABLE coaching_insights
            ADD COLUMN IF NOT EXISTS feedback      TEXT CHECK (feedback IN ('good', 'bad')),
            ADD COLUMN IF NOT EXISTS feedback_note TEXT
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE coaching_insights DROP COLUMN IF EXISTS feedback_note")
    op.execute("ALTER TABLE coaching_insights DROP COLUMN IF EXISTS feedback")
    op.execute("DROP TABLE IF EXISTS circuit_corner_knowledge")

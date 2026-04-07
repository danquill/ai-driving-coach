"""Add circuit_corners table.

Revision ID: 005
Revises: 004
Create Date: 2026-04-05 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision: str = "005"
down_revision: str = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS circuit_corners (
            id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            circuit_id  UUID NOT NULL REFERENCES circuits(id) ON DELETE CASCADE,
            corner_number SMALLINT NOT NULL,
            name        TEXT,
            distance_m  NUMERIC(10,2) NOT NULL,
            lat         DOUBLE PRECISION NOT NULL,
            lon         DOUBLE PRECISION NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (circuit_id, corner_number)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_circuit_corners_circuit_id ON circuit_corners(circuit_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS circuit_corners")

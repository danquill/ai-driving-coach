"""Add apexsession to raw_files file_format check constraint.

Revision ID: 010
Revises: 009
Create Date: 2026-04-12
"""

from __future__ import annotations

from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE raw_files DROP CONSTRAINT raw_files_file_format_check")
    op.execute("""
        ALTER TABLE raw_files ADD CONSTRAINT raw_files_file_format_check
        CHECK (file_format = ANY (ARRAY['vbo','drk','xdrk','ld','csv','apexsession']))
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE raw_files DROP CONSTRAINT raw_files_file_format_check")
    op.execute("""
        ALTER TABLE raw_files ADD CONSTRAINT raw_files_file_format_check
        CHECK (file_format = ANY (ARRAY['vbo','drk','xdrk','ld','csv']))
    """)

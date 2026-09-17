"""add run sid and source

Revision ID: 20260917_0002
Revises: 20260914_0001
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260917_0002"
down_revision: str | Sequence[str] | None = "20260914_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("runs")}
    indexes = {idx["name"] for idx in insp.get_indexes("runs")}
    if "sid" not in cols:
        op.add_column("runs", sa.Column("sid", sa.String(16), nullable=True))
    if "source" not in cols:
        op.add_column(
            "runs",
            sa.Column("source", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        )
    op.execute(
        sa.text(
            """
            UPDATE runs
            SET sid = lower(substr(replace(id::text, '-', ''), 1, 12))
            WHERE sid IS NULL OR BTRIM(sid) = ''
            """
        )
    )
    op.execute(sa.text("UPDATE runs SET source = '{}'::jsonb || jsonb_build_object('kind', 'cli') WHERE source = '{}'::jsonb OR source IS NULL"))
    op.alter_column("runs", "sid", existing_type=sa.String(16), nullable=False)
    if "ix_runs_sid" not in indexes and "runs_sid_key" not in indexes:
        op.create_index("ix_runs_sid", "runs", ["sid"], unique=True)


def downgrade() -> None:
    raise NotImplementedError("run sid/source is not reversible")

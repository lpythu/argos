"""baseline dash tables

Revision ID: 20260914_0001
Revises:
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260914_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("login", sa.String(64), nullable=False),
            sa.Column("password_hash", sa.String(256), nullable=False),
            sa.Column("name", sa.String(128), nullable=False, server_default=""),
            sa.UniqueConstraint("login"),
        )
    if "runs" not in tables:
        op.create_table(
            "runs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("stamp", sa.String(32), nullable=False, server_default=""),
            sa.Column("slug", sa.String(128), nullable=False, server_default=""),
            sa.Column("mode", sa.String(16), nullable=False, server_default="once"),
            sa.Column("env", sa.String(32), nullable=False, server_default=""),
            sa.Column("status", sa.String(16), nullable=False, server_default="running"),
            sa.Column("runner", sa.String(128), nullable=False, server_default=""),
            sa.Column("queries", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("packs", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("summary", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "cases" not in tables:
        op.create_table(
            "cases",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("spec_id", sa.String(128), nullable=False),
            sa.Column("slug", sa.String(128), nullable=False, server_default=""),
            sa.Column("title", sa.String(256), nullable=False, server_default=""),
            sa.Column("group", sa.String(64), nullable=False, server_default=""),
            sa.Column("pack", sa.String(64), nullable=False, server_default=""),
            sa.Column("iteration", sa.Integer, nullable=False, server_default="0"),
            sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
            sa.Column("error", sa.Text, nullable=False, server_default=""),
            sa.Column("elapsed_s", sa.Float, nullable=False, server_default="0"),
            sa.Column("steps", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("metrics", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        )
    if "comments" not in tables:
        op.create_table(
            "comments",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("case_id", sa.String(128), nullable=False, server_default=""),
            sa.Column("body", sa.Text, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )


def downgrade() -> None:
    raise NotImplementedError("dash baseline is not reversible")

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    login: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="")

    comments: Mapped[list["Comment"]] = relationship(back_populates="author")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stamp: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    slug: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="once")
    env: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    runner: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    queries: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    packs: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cases: Mapped[list["CaseRow"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    comments: Mapped[list["Comment"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class CaseRow(Base):
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    spec_id: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    group: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    pack: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    iteration: Mapped[int] = mapped_column(nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    elapsed_s: Mapped[float] = mapped_column(nullable=False, default=0)
    steps: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    run: Mapped["Run"] = relationship(back_populates="cases")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    case_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped["Run"] = relationship(back_populates="comments")
    author: Mapped["User"] = relationship(back_populates="comments")

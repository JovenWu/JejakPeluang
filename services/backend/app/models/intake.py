from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class Submission(Base):
    __tablename__ = 'submissions'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    ref: Mapped[str] = mapped_column(String(16), unique=True)
    receipt_token_hash: Mapped[str] = mapped_column(String(64))
    submitted_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    context: Mapped[str] = mapped_column(Text, default='')
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    state: Mapped[str] = mapped_column(String(32), default='received')
    client_net_hash: Mapped[str] = mapped_column(String(64))
    purge_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Upload(Base):
    __tablename__ = 'uploads'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    submission_id: Mapped[UUID] = mapped_column(ForeignKey('submissions.id'))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    detected_mime: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64))
    delete_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ScreeningRun(Base):
    __tablename__ = 'screening_runs'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    submission_id: Mapped[UUID] = mapped_column(ForeignKey('submissions.id'))
    state: Mapped[str] = mapped_column(String(32), default='queued')
    provider_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    schema_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),
        nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),
        nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class JobOutbox(Base):
    __tablename__ = 'job_outbox'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(64))
    screening_run_id: Mapped[UUID] = mapped_column(ForeignKey('screening_runs.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)


class CommunityReport(Base):
    __tablename__ = 'community_reports'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    opportunity_id: Mapped[UUID] = mapped_column(ForeignKey('opportunities.id'))
    category: Mapped[str] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default='open')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

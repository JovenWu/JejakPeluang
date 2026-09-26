from datetime import date, datetime
from uuid import UUID, uuid4
from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


class Issuer(Base):
    __tablename__ = 'issuers'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160))


class IssuerDomain(Base):
    __tablename__ = 'issuer_domains'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    issuer_id: Mapped[UUID] = mapped_column(ForeignKey('issuers.id'))
    domain: Mapped[str] = mapped_column(String(255), unique=True)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verification_method: Mapped[str | None] = mapped_column(String(64), nullable=True)


class SourceEvidence(Base):
    __tablename__ = 'source_evidence'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    issuer_id: Mapped[UUID] = mapped_column(ForeignKey('issuers.id'))
    url: Mapped[str] = mapped_column(String(2048))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ModerationDecision(Base):
    __tablename__ = 'moderation_decisions'
    # One approved decision per submission, enforced at the row level —
    # the backstop for a concurrent double-approve race.
    __table_args__ = (Index('uq_moderation_decisions_one_approved',
        'submission_id', unique=True,
        sqlite_where=text("status = 'approved'"),
        postgresql_where=text("status = 'approved'")),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    # nullable: submission-scoped decisions (reject/expire/needs_more_evidence
    # on file-only intakes) may carry no source evidence; publish_approved
    # still refuses an approved decision whose evidence id is missing.
    source_evidence_id: Mapped[UUID | None] = mapped_column(
        ForeignKey('source_evidence.id'), nullable=True)
    submission_id: Mapped[UUID | None] = mapped_column(ForeignKey('submissions.id'),
        nullable=True)
    actor_id: Mapped[UUID] = mapped_column(Uuid)
    status: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Opportunity(Base):
    __tablename__ = 'opportunities'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    issuer_id: Mapped[UUID] = mapped_column(ForeignKey('issuers.id'))
    # nullable source chain: 'issuer_confirmed_private' listings carry no
    # public domain/evidence and must never expose a source_url.
    issuer_domain_id: Mapped[UUID | None] = mapped_column(
        ForeignKey('issuer_domains.id'), nullable=True)
    source_evidence_id: Mapped[UUID | None] = mapped_column(
        ForeignKey('source_evidence.id'), nullable=True)
    moderation_decision_id: Mapped[UUID] = mapped_column(ForeignKey('moderation_decisions.id'))
    slug: Mapped[str] = mapped_column(String(160), unique=True)
    title: Mapped[str] = mapped_column(String(240))
    category: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(String)
    eligibility: Mapped[str] = mapped_column(String)
    region: Mapped[str | None] = mapped_column(String(160), nullable=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    trust_basis: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    # None when screening produced no source-match signal (e.g. Jev gated off).
    ai_source_match: Mapped[bool | None] = mapped_column(nullable=True)
    issuer: Mapped[Issuer] = relationship()


class AuditEvent(Base):
    __tablename__ = 'audit_events'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    # nullable actor: anonymous actors (e.g. public community reports) have
    # no user id; moderator actions always set it.
    actor_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    # nullable: audit rows for non-opportunity entities (submissions) point at
    # entity_type/entity_id instead.
    opportunity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey('opportunities.id'), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(32), default='opportunity',
        server_default='opportunity')
    entity_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

from datetime import date, datetime
from uuid import UUID, uuid4
from sqlalchemy import Date, DateTime, ForeignKey, String, Text, Uuid
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
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_evidence_id: Mapped[UUID] = mapped_column(ForeignKey('source_evidence.id'))
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
    issuer_domain_id: Mapped[UUID] = mapped_column(ForeignKey('issuer_domains.id'))
    source_evidence_id: Mapped[UUID] = mapped_column(ForeignKey('source_evidence.id'))
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
    source_url: Mapped[str] = mapped_column(String(2048))
    trust_basis: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    issuer: Mapped[Issuer] = relationship()


class AuditEvent(Base):
    __tablename__ = 'audit_events'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column(Uuid)
    action: Mapped[str] = mapped_column(String(64))
    opportunity_id: Mapped[UUID] = mapped_column(ForeignKey('opportunities.id'))
    entity_type: Mapped[str] = mapped_column(String(32), default='opportunity',
        server_default='opportunity')
    entity_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

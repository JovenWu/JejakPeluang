from datetime import date, datetime
from urllib.parse import urlsplit
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from app.models.catalogue import AuditEvent, IssuerDomain, ModerationDecision, Opportunity, SourceEvidence
from app.schemas.opportunity import Category


class OpportunityFields(BaseModel):
    slug: str
    title: str
    category: Category
    description: str
    eligibility: str
    region: str | None = None
    deadline: date | None = None
    checked_at: datetime


class InvalidPublication(ValueError):
    pass


def publish_approved(session, *, issuer_id, evidence_id, source_url, decision_id,
        fields: OpportunityFields, ai_source_match: bool | None = None):
    evidence = session.get(SourceEvidence, evidence_id)
    decision = session.get(ModerationDecision, decision_id) if decision_id else None
    host = urlsplit(str(source_url)).hostname
    domain = session.scalar(select(IssuerDomain).where(
        IssuerDomain.issuer_id == issuer_id,
        IssuerDomain.domain == host,
        IssuerDomain.verified_at.is_not(None),
    ))
    if (urlsplit(str(source_url)).scheme not in ('http', 'https')
            or not domain or not evidence or evidence.issuer_id != issuer_id
            or evidence.url != source_url or not decision
            or decision.status != 'approved'
            or decision.source_evidence_id != evidence.id):
        raise InvalidPublication('Verified source and human approval required')
    item = Opportunity(issuer_id=issuer_id, issuer_domain_id=domain.id,
        source_evidence_id=evidence.id, moderation_decision_id=decision.id,
        source_url=source_url,
        verified_at=decision.decided_at, trust_basis='public_source',
        status='published', ai_source_match=ai_source_match,
        **fields.model_dump())
    session.add(item)
    session.flush()
    session.add(AuditEvent(actor_id=decision.actor_id, action='publish_opportunity',
        opportunity_id=item.id, created_at=decision.decided_at))
    session.flush()
    return item


def publish_private_confirmed(session, *, issuer_id, decision_id,
        fields: OpportunityFields):
    """Publish an issuer-confirmed private notice.

    Same gate as publish_approved — a human 'approved' decision is required —
    but the trust basis is a moderator-attested private confirmation, so no
    domain, evidence, or source_url is attached (or ever surfaced).
    """
    decision = session.get(ModerationDecision, decision_id) if decision_id else None
    if not decision or decision.status != 'approved':
        raise InvalidPublication('Human approval required')
    item = Opportunity(issuer_id=issuer_id, issuer_domain_id=None,
        source_evidence_id=None, moderation_decision_id=decision.id,
        source_url=None,
        verified_at=decision.decided_at,
        trust_basis='issuer_confirmed_private', status='published',
        ai_source_match=None, **fields.model_dump())
    session.add(item)
    session.flush()
    session.add(AuditEvent(actor_id=decision.actor_id, action='publish_opportunity',
        opportunity_id=item.id, created_at=decision.decided_at))
    session.flush()
    return item


def reviewed_query():
    return (select(Opportunity)
        .join(ModerationDecision, Opportunity.moderation_decision_id == ModerationDecision.id)
        .outerjoin(IssuerDomain, Opportunity.issuer_domain_id == IssuerDomain.id)
        .options(selectinload(Opportunity.issuer))
        .where(ModerationDecision.status == 'approved'))


def list_public(session, *, category, q, limit, offset):
    statement = reviewed_query().where(Opportunity.status == 'published')
    if category:
        statement = statement.where(Opportunity.category == category)
    if q:
        statement = statement.where(Opportunity.title.ilike(f'%{q}%'))
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    items = session.scalars(statement.order_by(
        Opportunity.deadline.is_(None), Opportunity.deadline, Opportunity.slug
    ).limit(limit).offset(offset)).all()
    return items, total


def get_public(session, slug):
    return session.scalar(reviewed_query().where(
        Opportunity.slug == slug,
        Opportunity.status.in_(('published', 'expired', 'needs_review'))))

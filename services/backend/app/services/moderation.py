import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.catalogue import (AuditEvent, Issuer, IssuerDomain,
    ModerationDecision, Opportunity, SourceEvidence)
from app.models.intake import (CommunityReport, ScreeningRun, Submission,
    Upload)
from app.schemas.moderation import DecisionFields
from app.services.catalogue import (InvalidPublication, OpportunityFields,
    publish_approved, publish_private_confirmed)
from app.services.submissions import (SubmissionError, upload_root,
    validate_url)

DECISION_PURGE_DAYS = 7
TERMINAL_STATES = {'rejected', 'expired', 'closed_unreviewed', 'published'}
SLUG_FALLBACK = 'peluang'

_SLUG_RE = re.compile(r'[^a-z0-9]+')


class ModerationError(Exception):
    """Domain rejection; the API layer maps it to HTTPException."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def slugify(title: str) -> str:
    return _SLUG_RE.sub('-', title.lower()).strip('-') or SLUG_FALLBACK


def list_queue(session: Session, *, state: str | None, limit: int,
        offset: int) -> tuple[list[dict], int]:
    """Paginated moderation queue, oldest submissions first."""
    statement = select(Submission)
    if state:
        statement = statement.where(Submission.state == state)
    total = session.scalar(
        select(func.count()).select_from(statement.subquery())) or 0
    submissions = session.scalars(statement.order_by(
        Submission.created_at, Submission.ref).limit(limit).offset(
        offset)).all()
    ids = [submission.id for submission in submissions]
    upload_counts: dict = {}
    report_counts: dict = {}
    if ids:
        upload_counts = dict(session.execute(
            select(Upload.submission_id, func.count())
            .where(Upload.submission_id.in_(ids))
            .group_by(Upload.submission_id)).all())
        # reports target opportunities; the link to a submission runs through
        # the moderation_decision that published it.
        report_counts = dict(session.execute(
            select(ModerationDecision.submission_id,
                func.count(CommunityReport.id))
            .join(Opportunity,
                Opportunity.moderation_decision_id == ModerationDecision.id)
            .join(CommunityReport,
                CommunityReport.opportunity_id == Opportunity.id)
            .where(ModerationDecision.submission_id.in_(ids),
                CommunityReport.status == 'open')
            .group_by(ModerationDecision.submission_id)).all())
    items = [{
        'id': submission.id,
        'ref': submission.ref,
        'state': submission.state,
        'created_at': submission.created_at,
        'submitted_url_host': (urlsplit(submission.submitted_url).hostname
            if submission.submitted_url else None),
        'uploads_count': upload_counts.get(submission.id, 0),
        'has_contact_email': submission.contact_email is not None,
        'open_reports_count': report_counts.get(submission.id, 0),
    } for submission in submissions]
    return items, total


def detail_view(session: Session, submission: Submission) -> dict:
    """Full evidence projection; receipt_token_hash stays out by construction."""
    uploads = session.scalars(select(Upload).where(
        Upload.submission_id == submission.id).order_by(
        Upload.storage_key)).all()
    run = session.scalar(select(ScreeningRun).where(
        ScreeningRun.submission_id == submission.id).order_by(
        ScreeningRun.created_at.desc()).limit(1))
    decisions = session.scalars(select(ModerationDecision).where(
        ModerationDecision.submission_id == submission.id).order_by(
        ModerationDecision.decided_at.desc())).all()
    opportunity = session.scalar(select(Opportunity).join(
        ModerationDecision,
        Opportunity.moderation_decision_id == ModerationDecision.id).where(
        ModerationDecision.submission_id == submission.id))
    reports = []
    if opportunity is not None:
        reports = session.scalars(select(CommunityReport).where(
            CommunityReport.opportunity_id == opportunity.id).order_by(
            CommunityReport.created_at.desc())).all()
    return {
        'id': submission.id,
        'ref': submission.ref,
        'state': submission.state,
        'submitted_url': submission.submitted_url,
        'context': submission.context,
        'contact_email': submission.contact_email,
        'client_net_hash': submission.client_net_hash,
        'purge_after': submission.purge_after,
        'created_at': submission.created_at,
        'updated_at': submission.updated_at,
        'uploads': [{
            'id': upload.id,
            'storage_key': upload.storage_key,
            'detected_mime': upload.detected_mime,
            'size_bytes': upload.size_bytes,
            'page_count': upload.page_count,
        } for upload in uploads],
        'screening_run': {
            'id': run.id,
            'state': run.state,
            'provider_version': run.provider_version,
            'model_version': run.model_version,
            'schema_version': run.schema_version,
            'result_json': run.result_json,
            'error': run.error,
            'finished_at': run.finished_at,
            'created_at': run.created_at,
        } if run else None,
        'decisions': [{
            'id': decision.id,
            'status': decision.status,
            'reason': decision.reason,
            'actor_id': decision.actor_id,
            'decided_at': decision.decided_at,
        } for decision in decisions],
        'linked_opportunity_slug': opportunity.slug if opportunity else None,
        'reports': [{
            'id': report.id,
            'category': report.category,
            'description': report.description,
            'status': report.status,
            'created_at': report.created_at,
        } for report in reports],
    }


def upload_file_path(upload: Upload) -> Path | None:
    """Resolve an upload's storage_key inside UPLOAD_DIR, or None.

    storage_key is server-generated, but we still verify containment so a
    tampered row can never escape the upload root.
    """
    root = upload_root().resolve()
    candidate = (root / upload.storage_key).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        return None
    return candidate


def _issuer_by_name(session: Session, name: str) -> Issuer:
    issuer = session.scalar(select(Issuer).where(
        func.lower(Issuer.name) == func.lower(name)))
    if issuer is None:
        issuer = Issuer(name=name)
        session.add(issuer)
        session.flush()
    return issuer


def _resolve_issuer(session: Session, *, host: str,
        issuer_name: str | None) -> tuple[Issuer, IssuerDomain | None]:
    domain = session.scalar(
        select(IssuerDomain).where(IssuerDomain.domain == host))
    if issuer_name is not None:
        name = issuer_name.strip()
        if not name:
            raise ModerationError(422, 'issuer_name must not be blank')
        issuer = _issuer_by_name(session, name)
    elif domain is not None:
        issuer = session.get(Issuer, domain.issuer_id)
    else:
        issuer = _issuer_by_name(session, host)
    return issuer, domain


def _resolve_slug(session: Session, fields: DecisionFields) -> str:
    if fields.slug:
        if session.scalar(select(Opportunity.id).where(
                Opportunity.slug == fields.slug)):
            raise ModerationError(409, 'Slug is already in use')
        return fields.slug
    base = slugify(fields.title)
    slug = base
    suffix = 2
    while session.scalar(select(Opportunity.id).where(
            Opportunity.slug == slug)):
        slug = f'{base}-{suffix}'
        suffix += 1
    return slug


def _latest_ai_source_match(session: Session,
        submission: Submission) -> bool | None:
    """Read the badge flag off the newest completed screening run, if any."""
    run = session.scalar(select(ScreeningRun).where(
        ScreeningRun.submission_id == submission.id).order_by(
        ScreeningRun.created_at.desc()).limit(1))
    if run is None or not isinstance(run.result_json, dict):
        return None
    match = run.result_json.get('ai_source_match')
    return match if isinstance(match, bool) else None


def _approve(session: Session, *, submission: Submission, moderator: User,
        reason: str | None, fields: DecisionFields | None,
        now: datetime) -> tuple[ModerationDecision, Opportunity]:
    if fields is None:
        raise ModerationError(422, 'Approval requires opportunity fields')
    opportunity_fields = OpportunityFields(slug=_resolve_slug(session, fields),
        title=fields.title, category=fields.category,
        description=fields.description, eligibility=fields.eligibility,
        region=fields.region, deadline=fields.deadline, checked_at=now)
    if fields.trust_basis == 'issuer_confirmed_private':
        if fields.issuer_name is None:
            raise ModerationError(422,
                'issuer_confirmed_private requires issuer_name')
        name = fields.issuer_name.strip()
        if not name:
            raise ModerationError(422, 'issuer_name must not be blank')
        issuer = _issuer_by_name(session, name)
        decision = ModerationDecision(source_evidence_id=None,
            submission_id=submission.id, actor_id=moderator.id,
            status='approved', reason=reason, decided_at=now)
        session.add(decision)
        session.flush()
        opportunity = publish_private_confirmed(session, issuer_id=issuer.id,
            decision_id=decision.id, fields=opportunity_fields)
        return decision, opportunity
    if not submission.submitted_url:
        raise ModerationError(422,
            'Approval requires a submitted url as public source')
    url = validate_url(submission.submitted_url)
    if url is None:
        raise ModerationError(422, 'Submitted url is not usable as source')
    host = urlsplit(url).hostname
    issuer, domain = _resolve_issuer(session, host=host,
        issuer_name=fields.issuer_name)
    if domain is not None and domain.issuer_id != issuer.id:
        raise ModerationError(409,
            'Submitted domain is already attributed to a different issuer')
    if domain is None:
        domain = IssuerDomain(issuer_id=issuer.id, domain=host,
            verified_at=now, verification_method='moderator_confirmed')
        session.add(domain)
    else:
        domain.verified_at = now
        domain.verification_method = 'moderator_confirmed'
    evidence = SourceEvidence(issuer_id=issuer.id, url=url, retrieved_at=now)
    session.add(evidence)
    session.flush()
    decision = ModerationDecision(source_evidence_id=evidence.id,
        submission_id=submission.id, actor_id=moderator.id,
        status='approved', reason=reason, decided_at=now)
    session.add(decision)
    session.flush()
    opportunity = publish_approved(session, issuer_id=issuer.id,
        evidence_id=evidence.id, source_url=url, decision_id=decision.id,
        fields=opportunity_fields,
        ai_source_match=_latest_ai_source_match(session, submission))
    return decision, opportunity


def _shorten_upload_retention(session: Session, submission: Submission,
        until: datetime) -> None:
    """Couple upload retention to the (shortened) submission purge date."""
    uploads = session.scalars(select(Upload).where(
        Upload.submission_id == submission.id)).all()
    for upload in uploads:
        existing = upload.delete_after
        if existing is not None and existing.tzinfo is None:
            existing = existing.replace(tzinfo=timezone.utc)
        if existing is None or existing > until:
            upload.delete_after = until


def decide(session: Session, *, submission: Submission, moderator: User,
        action: str, reason: str | None,
        fields: DecisionFields | None) -> tuple[ModerationDecision,
        Opportunity | None]:
    """Record a moderation decision and its effects in one transaction.

    ``approved`` builds the full trust chain (issuer, verified domain,
    source evidence, decision) and delegates publication to
    ``publish_approved`` — its invariants are never bypassed. Non-approved
    decisions only move the submission state; ``rejected``/``expire`` are
    terminal and shorten retention to seven days.
    """
    if submission.state in TERMINAL_STATES:
        raise ModerationError(409,
            'Submission already reached a terminal state')
    if session.scalar(select(ModerationDecision.id).where(
            ModerationDecision.submission_id == submission.id,
            ModerationDecision.status == 'approved')):
        raise ModerationError(409,
            'Submission already has an approved decision')
    now = datetime.now(timezone.utc)
    try:
        opportunity = None
        if action == 'approved':
            decision, opportunity = _approve(session, submission=submission,
                moderator=moderator, reason=reason, fields=fields, now=now)
            submission.state = 'published'
        else:
            decision = ModerationDecision(source_evidence_id=None,
                submission_id=submission.id, actor_id=moderator.id,
                status=action, reason=reason, decided_at=now)
            session.add(decision)
            if action == 'needs_more_evidence':
                submission.state = 'review_pending'
            else:
                submission.state = ('expired' if action == 'expire'
                    else 'rejected')
                submission.purge_after = now + timedelta(
                    days=DECISION_PURGE_DAYS)
                _shorten_upload_retention(session, submission,
                    submission.purge_after)
        submission.updated_at = now
        session.add(AuditEvent(actor_id=moderator.id,
            action='moderation_decision', opportunity_id=None,
            entity_type='submission', entity_id=submission.id,
            created_at=now))
        session.commit()
    except ModerationError:
        session.rollback()
        raise
    except SubmissionError as exc:
        # A stored submitted_url that fails intake validation is a domain
        # rejection, not a server fault — map it before it escapes as a 500.
        session.rollback()
        raise ModerationError(422, exc.detail)
    except InvalidPublication as exc:
        session.rollback()
        raise ModerationError(422, str(exc))
    except IntegrityError:
        # The partial unique index on approved decisions is the backstop for
        # a concurrent double-approve; surface it as a conflict, not a 500.
        session.rollback()
        raise ModerationError(409,
            'Submission already has an approved decision')
    except Exception:
        session.rollback()
        raise
    return decision, opportunity


def create_report(session: Session, *, opportunity: Opportunity,
        category: str, description: str | None) -> CommunityReport:
    """File a community report against a listing.

    Reports flag a queue; they never mutate the opportunity's status or
    trust fields, and the actor stays anonymous (audit actor_id NULL).
    """
    now = datetime.now(timezone.utc)
    report = CommunityReport(opportunity_id=opportunity.id,
        category=category, description=description, status='open',
        created_at=now)
    session.add(report)
    session.add(AuditEvent(actor_id=None, action='community_report',
        opportunity_id=opportunity.id, entity_type='opportunity',
        entity_id=opportunity.id, created_at=now))
    session.commit()
    return report

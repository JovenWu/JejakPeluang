import pytest
from sqlalchemy import select
from uuid import uuid4
from app.models.catalogue import AuditEvent, Issuer, SourceEvidence
from app.services.catalogue import InvalidPublication, publish_approved


def test_rejects_unverified_domain(session, verified_issuer, official_source, approved_decision, valid_fields):
    with pytest.raises(InvalidPublication):
        publish_approved(session, issuer_id=verified_issuer.id,
            evidence_id=official_source.id, source_url='https://not-official.invalid/notice',
            decision_id=approved_decision.id, fields=valid_fields)


def test_rejects_non_http_source_url(session, verified_issuer, official_source,
        approved_decision, valid_fields):
    official_source.url = 'ftp://example.org/notice'
    session.flush()
    with pytest.raises(InvalidPublication):
        publish_approved(session, issuer_id=verified_issuer.id,
            evidence_id=official_source.id, source_url='ftp://example.org/notice',
            decision_id=approved_decision.id, fields=valid_fields)


def test_rejects_missing_approval(session, verified_issuer, official_source, valid_fields):
    with pytest.raises(InvalidPublication):
        publish_approved(session, issuer_id=verified_issuer.id,
            evidence_id=official_source.id, source_url=official_source.url,
            decision_id=None, fields=valid_fields)


@pytest.mark.parametrize('mode', ['missing_evidence', 'foreign_issuer', 'url_mismatch'])
def test_rejects_broken_evidence_chain(session, verified_issuer, official_source,
        approved_decision, valid_fields, mode):
    kwargs = dict(issuer_id=verified_issuer.id, evidence_id=official_source.id,
        source_url=official_source.url, decision_id=approved_decision.id)
    if mode == 'missing_evidence':
        kwargs['evidence_id'] = uuid4()
    elif mode == 'foreign_issuer':
        other = Issuer(name='Other Foundation')
        session.add(other)
        session.flush()
        official_source.issuer_id = other.id
        session.flush()
    elif mode == 'url_mismatch':
        kwargs['source_url'] = 'https://example.org/different-notice'
    with pytest.raises(InvalidPublication):
        publish_approved(session, fields=valid_fields, **kwargs)


@pytest.mark.parametrize('status', ['rejected', 'needs_evidence'])
def test_rejects_unapproved_decision(session, verified_issuer, official_source,
        approved_decision, valid_fields, status):
    approved_decision.status = status
    session.flush()
    with pytest.raises(InvalidPublication):
        publish_approved(session, issuer_id=verified_issuer.id,
            evidence_id=official_source.id, source_url=official_source.url,
            decision_id=approved_decision.id, fields=valid_fields)


def test_rejects_decision_for_other_evidence(session, verified_issuer, official_source,
        approved_decision, valid_fields):
    other = SourceEvidence(issuer_id=verified_issuer.id,
        url='https://example.org/other', retrieved_at=official_source.retrieved_at)
    session.add(other)
    session.flush()
    approved_decision.source_evidence_id = other.id
    session.flush()
    with pytest.raises(InvalidPublication):
        publish_approved(session, issuer_id=verified_issuer.id,
            evidence_id=official_source.id, source_url=official_source.url,
            decision_id=approved_decision.id, fields=valid_fields)


def test_accepts_reviewed_source(session, verified_issuer, official_source, approved_decision, valid_fields):
    item = publish_approved(session, issuer_id=verified_issuer.id,
        evidence_id=official_source.id, source_url=official_source.url,
        decision_id=approved_decision.id, fields=valid_fields)
    assert item.source_evidence_id == official_source.id
    assert item.status == 'published'
    event = session.scalar(select(AuditEvent).where(AuditEvent.opportunity_id == item.id))
    assert event is not None and event.action == 'publish_opportunity'

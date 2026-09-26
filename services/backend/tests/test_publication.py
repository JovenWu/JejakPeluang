import pytest
from sqlalchemy import select
from app.models.catalogue import AuditEvent
from app.services.catalogue import InvalidPublication, publish_approved


def test_rejects_unverified_domain(session, verified_issuer, official_source, approved_decision, valid_fields):
    with pytest.raises(InvalidPublication):
        publish_approved(session, issuer_id=verified_issuer.id,
            evidence_id=official_source.id, source_url='https://not-official.invalid/notice',
            decision_id=approved_decision.id, fields=valid_fields)


def test_rejects_missing_approval(session, verified_issuer, official_source, valid_fields):
    with pytest.raises(InvalidPublication):
        publish_approved(session, issuer_id=verified_issuer.id,
            evidence_id=official_source.id, source_url=official_source.url,
            decision_id=None, fields=valid_fields)


def test_accepts_reviewed_source(session, verified_issuer, official_source, approved_decision, valid_fields):
    item = publish_approved(session, issuer_id=verified_issuer.id,
        evidence_id=official_source.id, source_url=official_source.url,
        decision_id=approved_decision.id, fields=valid_fields)
    assert item.source_evidence_id == official_source.id
    assert item.status == 'published'
    event = session.scalar(select(AuditEvent).where(AuditEvent.opportunity_id == item.id))
    assert event is not None and event.action == 'publish_opportunity'

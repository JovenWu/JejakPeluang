from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select
from app.db import Base
from app.models.auth import AccessToken, User
from app.models.catalogue import AuditEvent, IssuerDomain, ModerationDecision
from app.models.intake import CommunityReport, JobOutbox, ScreeningRun, Submission, Upload

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


def make_submission(session):
    submission = Submission(ref='A1B2C3D4', receipt_token_hash='r' * 64,
        submitted_url='https://example.org/post', contact_email='guest@example.org',
        client_net_hash='n' * 64, purge_after=NOW, created_at=NOW, updated_at=NOW)
    session.add(submission)
    session.flush()
    return submission


def test_submission_round_trip(session):
    submission = make_submission(session)
    row = session.scalar(select(Submission).where(Submission.ref == 'A1B2C3D4'))
    assert row.id == submission.id
    assert row.state == 'received'
    assert row.context == ''
    assert row.submitted_url == 'https://example.org/post'


def test_upload_round_trip(session):
    submission = make_submission(session)
    upload = Upload(submission_id=submission.id, storage_key='inbox/a1b2c3d4.pdf',
        detected_mime='application/pdf', size_bytes=2048, page_count=3,
        sha256='s' * 64, delete_after=NOW)
    session.add(upload)
    session.flush()
    row = session.scalar(select(Upload).where(Upload.storage_key == 'inbox/a1b2c3d4.pdf'))
    assert row.submission_id == submission.id
    assert row.page_count == 3


def test_screening_run_and_outbox_round_trip(session):
    submission = make_submission(session)
    run = ScreeningRun(submission_id=submission.id, provider_version='v1',
        model_version='m1', schema_version='s1', created_at=NOW)
    session.add(run)
    session.flush()
    assert run.state == 'queued'
    job = JobOutbox(event_type='screening.completed', screening_run_id=run.id,
        created_at=NOW)
    session.add(job)
    session.flush()
    row = session.scalar(select(JobOutbox).where(JobOutbox.screening_run_id == run.id))
    assert row.attempts == 0
    assert row.delivered_at is None and row.last_error is None


def test_community_report_round_trip(session, make_entry):
    item = make_entry('report-target')
    report = CommunityReport(opportunity_id=item.id, category='deadline_wrong',
        description='Batas waktu berbeda', created_at=NOW)
    session.add(report)
    session.flush()
    row = session.scalar(select(CommunityReport).where(
        CommunityReport.opportunity_id == item.id))
    assert row.status == 'open'
    assert row.category == 'deadline_wrong'


def test_user_and_access_token_round_trip(session):
    user = User(email='mod@example.org', hashed_password='hashed')
    session.add(user)
    session.flush()
    token = AccessToken(token='tok-abc', user_id=user.id)
    session.add(token)
    session.flush()
    row = session.scalar(select(AccessToken).where(AccessToken.token == 'tok-abc'))
    assert row.user_id == user.id
    assert row.created_at is not None
    assert user.is_active and not user.is_superuser and not user.is_verified
    assert user.role == 'moderator'


def test_catalogue_extensions(session, official_source, make_entry):
    submission = make_submission(session)
    decision = ModerationDecision(source_evidence_id=official_source.id,
        submission_id=submission.id, actor_id=uuid4(), status='rejected',
        reason='spam', decided_at=NOW)
    session.add(decision)
    session.flush()
    assert decision.submission_id == submission.id and decision.reason == 'spam'
    domain = session.scalar(select(IssuerDomain).where(
        IssuerDomain.issuer_id == official_source.issuer_id))
    assert domain.verification_method is None
    domain.verification_method = 'moderator_confirmed'
    session.flush()
    item = make_entry('audit-target')
    event = session.scalar(select(AuditEvent).where(
        AuditEvent.opportunity_id == item.id))
    assert event.entity_type == 'opportunity'
    assert event.entity_id is None


def test_metadata_contains_new_tables():
    expected = {'submissions', 'uploads', 'screening_runs', 'job_outbox',
        'community_reports', 'users', 'access_tokens'}
    assert expected.issubset(Base.metadata.tables)
    assert 'submission_id' in Base.metadata.tables['moderation_decisions'].c
    assert 'reason' in Base.metadata.tables['moderation_decisions'].c
    assert 'verification_method' in Base.metadata.tables['issuer_domains'].c
    assert 'entity_type' in Base.metadata.tables['audit_events'].c
    assert 'entity_id' in Base.metadata.tables['audit_events'].c

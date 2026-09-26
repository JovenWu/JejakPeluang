import hashlib
import io
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from pypdf import PdfWriter
from sqlalchemy import func, select

from app.models.catalogue import (AuditEvent, Issuer, IssuerDomain,
    ModerationDecision, Opportunity, SourceEvidence)
from app.models.intake import (CommunityReport, ScreeningRun, Submission,
    Upload)
from app.security import rate_limiter

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)

QUEUE_URL = '/api/v1/moderation/submissions'
REPORTS_URL = '/api/v1/opportunities/{slug}/reports'
ORIGIN = {'Origin': 'http://testserver'}


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    rate_limiter.reset()
    yield
    rate_limiter.reset()


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    target = tmp_path / 'uploads'
    target.mkdir()
    monkeypatch.setenv('UPLOAD_DIR', str(target))
    return target


@pytest.fixture
def moderator(client, session, make_user, auth_cookie):
    user = make_user(f'mod-{uuid4().hex[:8]}@example.org')
    client.cookies.set('jp_auth', auth_cookie(user))
    return user


def make_submission(session, *, state='review_pending',
        url='https://example.org/program', contact_email='guest@example.org'):
    submission = Submission(ref=f'JP-{uuid4().hex[:8].upper()}',
        receipt_token_hash=hashlib.sha256(uuid4().bytes).hexdigest(),
        submitted_url=url, context='Ada poster terlampir',
        contact_email=contact_email, state=state,
        client_net_hash='n' * 64, purge_after=NOW + timedelta(days=30),
        created_at=NOW, updated_at=NOW)
    session.add(submission)
    session.flush()
    run = ScreeningRun(submission_id=submission.id, state='queued',
        created_at=NOW)
    session.add(run)
    session.commit()
    return submission


def make_upload(session, submission, storage_key=None, data=b'%PDF-1.4 fake'):
    key = storage_key or f'{uuid4().hex}.pdf'
    upload = Upload(submission_id=submission.id, storage_key=key,
        detected_mime='application/pdf', size_bytes=len(data), page_count=1,
        sha256=hashlib.sha256(data).hexdigest(),
        delete_after=NOW + timedelta(days=30))
    session.add(upload)
    session.commit()
    return upload


def pdf_file():
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def decide(client, submission_id, payload):
    return client.post(f'{QUEUE_URL}/{submission_id}/decision', json=payload,
        headers=ORIGIN)


def approve_fields(**overrides):
    fields = {'title': 'Beasiswa Uji', 'category': 'scholarship',
        'description': 'Program beasiswa uji', 'eligibility': 'Pelajar SMA'}
    fields.update(overrides)
    return {'decision': 'approved', 'reason': 'Verified official page',
        'fields': fields}


# --- queue listing -------------------------------------------------------


def test_queue_requires_auth(client):
    assert client.get(QUEUE_URL).status_code == 401


def test_queue_forbids_non_moderator(client, make_user, auth_cookie):
    user = make_user('viewer@example.org', role='viewer')
    client.cookies.set('jp_auth', auth_cookie(user))
    assert client.get(QUEUE_URL).status_code == 403


def test_queue_lists_submissions(client, session, moderator):
    submission = make_submission(session)
    make_upload(session, submission)
    other = make_submission(session, url=None, contact_email=None)
    response = client.get(QUEUE_URL)
    assert response.status_code == 200
    body = response.json()
    assert body['total'] == 2
    rows = {row['ref']: row for row in body['items']}
    row = rows[submission.ref]
    assert row['id'] == str(submission.id)
    assert row['state'] == 'review_pending'
    assert row['submitted_url_host'] == 'example.org'
    assert row['uploads_count'] == 1
    assert row['has_contact_email'] is True
    assert row['open_reports_count'] == 0
    # guest PII stays out of list rows
    assert 'contact_email' not in row
    other_row = rows[other.ref]
    assert other_row['submitted_url_host'] is None
    assert other_row['uploads_count'] == 0
    assert other_row['has_contact_email'] is False


def test_queue_filters_by_state(client, session, moderator):
    pending = make_submission(session, state='review_pending')
    make_submission(session, state='queued')
    response = client.get(QUEUE_URL, params={'state': 'review_pending'})
    assert response.status_code == 200
    body = response.json()
    assert body['total'] == 1
    assert [row['ref'] for row in body['items']] == [pending.ref]


def test_queue_paginates(client, session, moderator):
    for _ in range(3):
        make_submission(session)
    page = client.get(QUEUE_URL, params={'limit': 2, 'offset': 0})
    assert page.status_code == 200
    assert page.json()['total'] == 3
    assert len(page.json()['items']) == 2
    rest = client.get(QUEUE_URL, params={'limit': 2, 'offset': 2})
    assert len(rest.json()['items']) == 1


def test_queue_counts_open_reports(client, session, moderator, make_entry):
    submission = make_submission(session)
    item = make_entry('reported-listing')
    decision = session.get(ModerationDecision, item.moderation_decision_id)
    decision.submission_id = submission.id
    session.flush()
    session.add(CommunityReport(opportunity_id=item.id,
        category='link_broken', status='open', created_at=NOW))
    session.add(CommunityReport(opportunity_id=item.id,
        category='other', status='resolved', created_at=NOW))
    session.flush()
    response = client.get(QUEUE_URL)
    row = response.json()['items'][0]
    assert row['open_reports_count'] == 1


# --- submission detail ----------------------------------------------------


def test_detail_requires_auth(client, session):
    submission = make_submission(session)
    assert client.get(f'{QUEUE_URL}/{submission.id}').status_code == 401


def test_detail_forbids_non_moderator(client, session, make_user, auth_cookie):
    user = make_user('viewer@example.org', role='viewer')
    client.cookies.set('jp_auth', auth_cookie(user))
    submission = make_submission(session)
    assert client.get(f'{QUEUE_URL}/{submission.id}').status_code == 403


def test_detail_unknown_submission_404(client, moderator):
    assert client.get(f'{QUEUE_URL}/{uuid4()}').status_code == 404


def test_detail_returns_full_evidence(client, session, moderator, upload_dir):
    submission = make_submission(session)
    data = pdf_file()
    upload = make_upload(session, submission, data=data)
    (upload_dir / upload.storage_key).write_bytes(data)
    response = client.get(f'{QUEUE_URL}/{submission.id}')
    assert response.status_code == 200
    body = response.json()
    assert body['id'] == str(submission.id)
    assert body['ref'] == submission.ref
    assert body['state'] == 'review_pending'
    assert body['submitted_url'] == 'https://example.org/program'
    assert body['contact_email'] == 'guest@example.org'
    assert body['context'] == 'Ada poster terlampir'
    assert 'receipt_token_hash' not in body
    assert body['uploads'] == [{
        'id': str(upload.id),
        'storage_key': upload.storage_key,
        'detected_mime': 'application/pdf',
        'size_bytes': len(data),
        'page_count': 1,
    }]
    assert body['screening_run']['state'] == 'queued'
    assert body['decisions'] == []
    assert body['reports'] == []


def test_download_requires_auth(client, session):
    submission = make_submission(session)
    upload = make_upload(session, submission)
    response = client.get(
        f'{QUEUE_URL}/{submission.id}/uploads/{upload.id}')
    assert response.status_code == 401


def test_download_streams_stored_file(client, session, moderator, upload_dir):
    submission = make_submission(session)
    data = pdf_file()
    upload = make_upload(session, submission, data=data)
    (upload_dir / upload.storage_key).write_bytes(data)
    response = client.get(
        f'{QUEUE_URL}/{submission.id}/uploads/{upload.id}')
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/pdf'
    assert response.content == data


def test_download_rejects_foreign_submission(client, session, moderator,
        upload_dir):
    submission = make_submission(session)
    other = make_submission(session)
    upload = make_upload(session, other)
    (upload_dir / upload.storage_key).write_bytes(pdf_file())
    response = client.get(
        f'{QUEUE_URL}/{submission.id}/uploads/{upload.id}')
    assert response.status_code == 404


def test_download_rejects_path_escape(client, session, moderator, upload_dir):
    submission = make_submission(session)
    outside = upload_dir.parent / 'secret.txt'
    outside.write_text('top secret')
    upload = make_upload(session, submission,
        storage_key='../secret.txt')
    response = client.get(
        f'{QUEUE_URL}/{submission.id}/uploads/{upload.id}')
    assert response.status_code == 404


def test_download_missing_file_404(client, session, moderator, upload_dir):
    submission = make_submission(session)
    upload = make_upload(session, submission)
    response = client.get(
        f'{QUEUE_URL}/{submission.id}/uploads/{upload.id}')
    assert response.status_code == 404


# --- decisions ------------------------------------------------------------


def test_decision_requires_auth(client, session):
    submission = make_submission(session)
    response = decide(client, submission.id, {'decision': 'rejected'})
    assert response.status_code == 401


def test_decision_forbids_non_moderator(client, session, make_user,
        auth_cookie):
    user = make_user('viewer@example.org', role='viewer')
    client.cookies.set('jp_auth', auth_cookie(user))
    submission = make_submission(session)
    response = decide(client, submission.id, {'decision': 'rejected'})
    assert response.status_code == 403


def test_decision_unknown_submission_404(client, moderator):
    response = decide(client, uuid4(), {'decision': 'rejected'})
    assert response.status_code == 404


def test_decision_rejects_unknown_value(client, session, moderator):
    submission = make_submission(session)
    response = decide(client, submission.id, {'decision': 'maybe'})
    assert response.status_code == 422


def test_needs_more_evidence_marks_review_pending(client, session, moderator):
    submission = make_submission(session, state='queued')
    response = decide(client, submission.id,
        {'decision': 'needs_more_evidence', 'reason': 'Bukti kurang'})
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'needs_more_evidence'
    assert body['submission_state'] == 'review_pending'
    session.expire_all()
    assert session.get(Submission, submission.id).state == 'review_pending'
    decision = session.scalar(select(ModerationDecision).where(
        ModerationDecision.submission_id == submission.id))
    assert decision.status == 'needs_more_evidence'
    assert decision.reason == 'Bukti kurang'
    assert decision.actor_id == moderator.id
    assert decision.source_evidence_id is None
    audit = session.scalar(select(AuditEvent).where(
        AuditEvent.entity_type == 'submission',
        AuditEvent.entity_id == submission.id))
    assert audit is not None and audit.actor_id == moderator.id
    assert audit.opportunity_id is None


@pytest.mark.parametrize('action,state', [
    ('rejected', 'rejected'), ('expire', 'expired')])
def test_terminal_decisions_set_purge_after(client, session, moderator,
        action, state):
    submission = make_submission(session)
    response = decide(client, submission.id, {'decision': action})
    assert response.status_code == 200
    assert response.json()['submission_state'] == state
    session.expire_all()
    row = session.get(Submission, submission.id)
    assert row.state == state
    # SQLite stores DateTime(timezone=True) without an offset — compare naive.
    delta = row.purge_after - datetime.now(timezone.utc).replace(tzinfo=None)
    assert timedelta(days=6, hours=23) < delta <= timedelta(days=7)


def test_decision_on_terminal_submission_conflicts(client, session, moderator):
    submission = make_submission(session, state='rejected')
    response = decide(client, submission.id, {'decision': 'approved'})
    assert response.status_code == 409


def test_approve_requires_submitted_url(client, session, moderator):
    submission = make_submission(session, url=None)
    response = decide(client, submission.id, approve_fields())
    assert response.status_code == 422


def test_approve_requires_fields(client, session, moderator):
    submission = make_submission(session)
    response = decide(client, submission.id, {'decision': 'approved'})
    assert response.status_code == 422


def test_approve_publishes_opportunity_end_to_end(client, session, moderator):
    submission = make_submission(session)
    response = decide(client, submission.id, approve_fields(
        issuer_name='Universitas Contoh', region='Jawa Barat',
        deadline='2026-12-31'))
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'approved'
    assert body['submission_state'] == 'review_pending'
    slug = body['opportunity_slug']
    assert slug == 'beasiswa-uji'

    item = session.scalar(select(Opportunity).where(Opportunity.slug == slug))
    assert item is not None
    assert item.status == 'published'
    assert item.title == 'Beasiswa Uji'
    assert item.issuer.name == 'Universitas Contoh'
    assert item.source_url == 'https://example.org/program'

    domain = session.scalar(select(IssuerDomain).where(
        IssuerDomain.id == item.issuer_domain_id))
    assert domain.domain == 'example.org'
    assert domain.verification_method == 'moderator_confirmed'
    assert domain.verified_at is not None

    evidence = session.get(SourceEvidence, item.source_evidence_id)
    assert evidence.url == 'https://example.org/program'
    assert evidence.issuer_id == item.issuer_id

    decision = session.get(ModerationDecision, item.moderation_decision_id)
    assert decision.submission_id == submission.id
    assert decision.status == 'approved'
    assert decision.reason == 'Verified official page'
    assert decision.actor_id == moderator.id

    decision_audit = session.scalar(select(AuditEvent).where(
        AuditEvent.entity_type == 'submission',
        AuditEvent.entity_id == submission.id))
    assert decision_audit is not None
    publish_audit = session.scalar(select(AuditEvent).where(
        AuditEvent.action == 'publish_opportunity',
        AuditEvent.opportunity_id == item.id))
    assert publish_audit is not None

    # the approved listing is publicly visible
    public = client.get(f'/api/v1/opportunities/{slug}')
    assert public.status_code == 200
    assert public.json()['title'] == 'Beasiswa Uji'
    assert public.json()['issuer_name'] == 'Universitas Contoh'


def test_approve_derives_issuer_from_domain(client, session, moderator):
    submission = make_submission(session,
        url='https://beasiswa.kampus.ac.id/info')
    response = decide(client, submission.id, approve_fields())
    assert response.status_code == 200
    item = session.scalar(select(Opportunity).where(
        Opportunity.slug == 'beasiswa-uji'))
    assert item.issuer.name == 'beasiswa.kampus.ac.id'
    domain = session.scalar(select(IssuerDomain).where(
        IssuerDomain.domain == 'beasiswa.kampus.ac.id'))
    assert domain.issuer_id == item.issuer_id
    assert domain.verification_method == 'moderator_confirmed'


def test_approve_reuses_existing_issuer_and_domain(client, session, moderator,
        verified_issuer):
    first = make_submission(session, url='https://example.org/a')
    second = make_submission(session, url='https://example.org/b')
    issuer_count = session.scalar(select(func.count()).select_from(Issuer))
    decide(client, first.id, approve_fields(
        slug='program-a', issuer_name='Example University'))
    decide(client, second.id, approve_fields(
        slug='program-b', issuer_name='Example University'))
    assert session.scalar(select(func.count()).select_from(Issuer)
        ) == issuer_count
    domains = session.scalars(select(IssuerDomain).where(
        IssuerDomain.domain == 'example.org')).all()
    assert len(domains) == 1
    assert domains[0].issuer_id == verified_issuer.id


def test_approve_explicit_slug_conflict(client, session, moderator,
        make_entry):
    make_entry('taken-slug')
    submission = make_submission(session)
    response = decide(client, submission.id,
        approve_fields(slug='taken-slug'))
    assert response.status_code == 409


def test_approve_slug_collision_autosuffixes(client, session, moderator,
        make_entry):
    make_entry('beasiswa-uji')
    submission = make_submission(session)
    response = decide(client, submission.id, approve_fields())
    assert response.status_code == 200
    assert response.json()['opportunity_slug'] == 'beasiswa-uji-2'


def test_double_approve_conflicts_and_publishes_once(client, session,
        moderator):
    submission = make_submission(session)
    assert decide(client, submission.id, approve_fields()).status_code == 200
    response = decide(client, submission.id, approve_fields(slug='lain'))
    assert response.status_code == 409
    assert session.scalar(select(func.count()).select_from(
        Opportunity)) == 1


def test_approve_blocked_domain_attribution_conflict(client, session,
        moderator, verified_issuer):
    # example.org is already verified for verified_issuer; naming a different
    # issuer must not silently reattribute the domain.
    submission = make_submission(session, url='https://example.org/x')
    response = decide(client, submission.id, approve_fields(
        issuer_name='Other Foundation'))
    assert response.status_code == 409
    assert session.scalar(select(func.count()).select_from(
        Opportunity)) == 0


def test_approve_rolls_back_on_failure(client, session, moderator,
        monkeypatch):
    submission = make_submission(session, state='queued')
    from app.services import catalogue as catalogue_service

    def boom(*args, **kwargs):
        raise catalogue_service.InvalidPublication('broken chain')

    monkeypatch.setattr('app.services.moderation.publish_approved', boom)
    response = decide(client, submission.id, approve_fields())
    assert response.status_code in (409, 422)
    session.expire_all()
    assert session.scalar(select(func.count()).select_from(
        Opportunity)) == 0
    assert session.scalar(select(func.count()).select_from(
        ModerationDecision)) == 0
    assert session.get(Submission, submission.id).state == 'queued'


def test_approve_stored_bad_url_is_422_not_500(client, session, moderator):
    # A stored submitted_url that fails intake validation (e.g. written
    # before the checks existed) must surface as 422, not escape as a 500.
    submission = make_submission(session, url='ftp://example.org/file')
    response = decide(client, submission.id, approve_fields())
    assert response.status_code == 422
    assert session.scalar(select(func.count()).select_from(
        Opportunity)) == 0
    assert session.scalar(select(func.count()).select_from(
        ModerationDecision)) == 0


def test_approve_blank_issuer_name_422(client, session, moderator):
    # Whitespace-only issuer_name must not create an empty Issuer row.
    submission = make_submission(session)
    response = decide(client, submission.id,
        approve_fields(issuer_name='   '))
    assert response.status_code == 422
    assert session.scalar(select(func.count()).select_from(Issuer)) == 0
    assert session.scalar(select(func.count()).select_from(
        ModerationDecision)) == 0


def test_detail_shows_decision_history_and_reports(client, session, moderator,
        make_entry):
    submission = make_submission(session)
    decide(client, submission.id, approve_fields(slug='linked-listing'))
    session.add(CommunityReport(opportunity_id=session.scalar(
        select(Opportunity.id).where(Opportunity.slug == 'linked-listing')),
        category='scam_suspect', description='Mencurigakan', status='open',
        created_at=NOW))
    session.flush()
    response = client.get(f'{QUEUE_URL}/{submission.id}')
    body = response.json()
    assert body['linked_opportunity_slug'] == 'linked-listing'
    assert [d['status'] for d in body['decisions']] == ['approved']
    assert len(body['reports']) == 1
    assert body['reports'][0]['category'] == 'scam_suspect'
    assert body['reports'][0]['description'] == 'Mencurigakan'


# --- community reports ------------------------------------------------------


def test_report_unknown_slug_404(client):
    response = client.post(REPORTS_URL.format(slug='nope'),
        json={'category': 'other'})
    assert response.status_code == 404


def test_report_created_returns_id_only(client, session, make_entry):
    item = make_entry('flagged-listing')
    response = client.post(REPORTS_URL.format(slug=item.slug),
        json={'category': 'deadline_wrong',
              'description': 'Batas waktu berbeda dengan poster'})
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {'id'}
    report = session.scalar(select(CommunityReport).where(
        CommunityReport.id == UUID(body['id'])))
    assert report.opportunity_id == item.id
    assert report.category == 'deadline_wrong'
    assert report.status == 'open'
    # report never mutates the listing
    assert session.get(Opportunity, item.id).status == 'published'
    audit = session.scalar(select(AuditEvent).where(
        AuditEvent.entity_type == 'opportunity',
        AuditEvent.entity_id == item.id,
        AuditEvent.action == 'community_report'))
    assert audit is not None
    assert audit.opportunity_id == item.id
    assert audit.actor_id is None


def test_report_rejects_bad_category(client, make_entry):
    item = make_entry('bad-category')
    response = client.post(REPORTS_URL.format(slug=item.slug),
        json={'category': 'rude'})
    assert response.status_code == 422


def test_report_description_bounded(client, make_entry):
    item = make_entry('long-description')
    response = client.post(REPORTS_URL.format(slug=item.slug),
        json={'category': 'other', 'description': 'x' * 2001})
    assert response.status_code == 422


def test_report_rate_limited(client, session, make_entry):
    item = make_entry('spam-limited')
    for _ in range(20):
        response = client.post(REPORTS_URL.format(slug=item.slug),
            json={'category': 'other'})
        assert response.status_code == 201
    response = client.post(REPORTS_URL.format(slug=item.slug),
        json={'category': 'other'})
    assert response.status_code == 429
    assert session.scalar(select(func.count()).select_from(
        CommunityReport)) == 20


# --- outbox dispatch wiring ------------------------------------------------


def test_dispatch_pending_defaults_to_logging_publisher(session, caplog):
    import logging
    from app.models.intake import JobOutbox
    from app.services.outbox import dispatch_pending

    submission = make_submission(session)
    run = session.scalar(select(ScreeningRun).where(
        ScreeningRun.submission_id == submission.id))
    session.add(JobOutbox(event_type='screening.requested',
        screening_run_id=run.id, created_at=NOW))
    session.flush()
    with caplog.at_level(logging.INFO):
        delivered = dispatch_pending(session)
    assert delivered == 1
    assert 'screening.requested' in caplog.text

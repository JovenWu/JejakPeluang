import hashlib
import io
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from pypdf import PdfWriter
from sqlalchemy import func, select

from app.models.catalogue import ModerationDecision
from app.models.intake import JobOutbox, ScreeningRun, Submission, Upload
from app.services import submissions as submissions_service

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    target = tmp_path / 'uploads'
    monkeypatch.setenv('UPLOAD_DIR', str(target))
    return target


def pdf_bytes(pages=1):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


PNG_BYTES = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64
JPG_BYTES = b'\xff\xd8\xff\xe0' + b'\x00' * 64


def pdf_part(name='laporan.pdf', pages=1):
    return ('files', (name, pdf_bytes(pages), 'application/pdf'))


def post(client, **kwargs):
    return client.post('/api/v1/submissions', **kwargs)


def test_submit_context_at_limit_accepted(client, session, upload_dir):
    limit = submissions_service.MAX_CONTEXT_LENGTH
    response = post(client, data={'url': 'https://example.org/program',
        'context': 'x' * limit})
    assert response.status_code == 202
    ref = response.json()['ref']
    submission = session.scalar(
        select(Submission).where(Submission.ref == ref))
    assert submission.context == 'x' * limit


def test_submit_context_over_limit_rejected(client, session, upload_dir):
    limit = submissions_service.MAX_CONTEXT_LENGTH
    response = post(client, data={'url': 'https://example.org/program',
        'context': 'x' * (limit + 1)})
    assert response.status_code == 422
    assert session.scalar(select(func.count()).select_from(Submission)) == 0


def test_submit_url_only_returns_202_and_rows(client, session, upload_dir):
    response = post(client, data={'url': 'https://example.org/program',
        'context': 'Sumber resmi', 'contact_email': 'guest@example.org'})
    assert response.status_code == 202
    body = response.json()
    assert re.fullmatch(r'JP-[0-9A-HJKMNP-TV-Z]{8}', body['ref'])
    assert body['receipt_token']
    assert body['status'] == 'queued'
    assert body['status_url'] == f"/api/v1/submissions/{body['ref']}"

    submission = session.scalar(
        select(Submission).where(Submission.ref == body['ref']))
    assert submission is not None
    assert submission.state == 'queued'
    assert submission.submitted_url == 'https://example.org/program'
    assert submission.context == 'Sumber resmi'
    assert submission.contact_email == 'guest@example.org'
    # Token is never persisted raw — only its sha256 hex.
    assert submission.receipt_token_hash != body['receipt_token']
    assert submission.receipt_token_hash == hashlib.sha256(
        body['receipt_token'].encode()).hexdigest()
    assert submission.purge_after - submission.created_at == timedelta(days=30)
    assert submission.client_net_hash

    run = session.scalar(select(ScreeningRun).where(
        ScreeningRun.submission_id == submission.id))
    assert run is not None and run.state == 'queued'
    job = session.scalar(select(JobOutbox).where(
        JobOutbox.screening_run_id == run.id))
    assert job is not None
    assert job.event_type == 'screening.requested'
    assert job.delivered_at is None and job.attempts == 0


def test_submit_file_only_pdf_stores_upload(client, session, upload_dir):
    data = pdf_bytes(3)
    response = post(client, files=[('files',
        ('laporan.pdf', data, 'application/pdf'))])
    assert response.status_code == 202
    upload = session.scalar(select(Upload))
    assert upload is not None
    assert re.fullmatch(r'[0-9a-f]{32}\.pdf', upload.storage_key)
    assert 'laporan' not in upload.storage_key
    assert upload.detected_mime == 'application/pdf'
    assert upload.size_bytes == len(data)
    assert upload.page_count == 3
    assert upload.sha256 == hashlib.sha256(data).hexdigest()
    assert (upload_dir / upload.storage_key).read_bytes() == data
    assert upload.delete_after is not None
    # Nothing left behind in staging.
    staging = upload_dir / 'staging'
    assert not staging.exists() or list(staging.iterdir()) == []


def test_submit_accepts_jpg_and_png(client, session, upload_dir):
    response = post(client, files=[
        ('files', ('a.jpg', JPG_BYTES, 'image/jpeg')),
        ('files', ('b.png', PNG_BYTES, 'image/png'))])
    assert response.status_code == 202
    uploads = session.scalars(select(Upload).order_by(Upload.storage_key)).all()
    assert {u.detected_mime for u in uploads} == {'image/jpeg', 'image/png'}
    assert all(u.page_count is None for u in uploads)


def test_submit_requires_url_or_file(client, upload_dir):
    assert post(client, data={}).status_code == 422


@pytest.mark.parametrize('url', ['ftp://example.org/x', 'javascript:alert(1)',
    'file:///etc/passwd', 'https://', 'http://exa mple.com/x'])
def test_submit_rejects_bad_url(client, upload_dir, url):
    assert post(client, data={'url': url}).status_code == 422


@pytest.mark.parametrize('url', [
    'http://127.0.0.1/x', 'http://127.0.0.1:8080/x', 'https://169.254.169.254/',
    'http://[::1]/x', 'http://[::ffff:127.0.0.1]/x', 'http://0x7f.0.0.1/x',
    'http://2130706433/x', 'http://127.1/x', 'http://user:pass@example.org/x',
    'http://user@example.org/x', 'https://example.org:8443/x',
    'http://example.org:8080/x'])
def test_submit_rejects_unsafe_url_hosts(client, upload_dir, url):
    assert post(client, data={'url': url}).status_code == 422


@pytest.mark.parametrize('url', [
    'http://example.org:80/x', 'https://example.org:443/x',
    'https://sub.domain.example.org/path?q=1#frag'])
def test_submit_accepts_safe_url_forms(client, session, upload_dir, url):
    assert post(client, data={'url': url}).status_code == 202
    submission = session.scalar(select(Submission).order_by(
        Submission.created_at.desc()))
    assert submission.submitted_url == url


def test_submit_rejects_bad_contact_email(client, upload_dir):
    response = post(client, data={'url': 'https://example.org/x',
        'contact_email': 'bukan-email'})
    assert response.status_code == 422


def test_submit_rejects_wrong_magic_bytes(client, session, upload_dir):
    response = post(client, files=[('files',
        ('palsu.pdf', b'GIF89a not really a pdf', 'application/pdf'))])
    assert response.status_code == 400
    assert session.scalar(select(func.count()).select_from(Submission)) == 0
    assert session.scalar(select(func.count()).select_from(Upload)) == 0
    staging = upload_dir / 'staging'
    assert not staging.exists() or list(staging.iterdir()) == []


def test_submit_rejects_more_than_three_files(client, upload_dir):
    files = [('files', (f'f{i}.png', PNG_BYTES, 'image/png')) for i in range(4)]
    assert post(client, files=files).status_code == 422


def test_submit_rejects_oversize_file(client, session, upload_dir):
    big = PNG_BYTES + b'\x00' * (10 * 1024 * 1024)
    response = post(client, files=[('files', ('big.png', big, 'image/png'))])
    assert response.status_code == 413
    assert session.scalar(select(func.count()).select_from(Submission)) == 0


def test_submit_rejects_oversize_combined(client, session, upload_dir):
    nine_mb = PNG_BYTES + b'\x00' * (9 * 1024 * 1024)
    four_mb = PNG_BYTES + b'\x00' * (4 * 1024 * 1024)
    files = [('files', ('a.png', nine_mb, 'image/png')),
        ('files', ('b.png', nine_mb, 'image/png')),
        ('files', ('c.png', four_mb, 'image/png'))]
    response = post(client, files=files)
    assert response.status_code == 413
    assert session.scalar(select(func.count()).select_from(Submission)) == 0
    staging = upload_dir / 'staging'
    assert not staging.exists() or list(staging.iterdir()) == []


def test_submit_rejects_pdf_over_15_pages(client, upload_dir):
    assert post(client, files=[pdf_part(pages=16)]).status_code == 400


def test_submit_rejects_corrupt_pdf(client, upload_dir):
    response = post(client, files=[('files',
        ('rusak.pdf', b'%PDF-1.4 but the rest is garbage', 'application/pdf'))])
    assert response.status_code == 400


def test_submit_cleans_up_when_scanner_rejects(client, session, upload_dir):
    class RejectingScanner:
        def scan(self, path):
            raise RuntimeError('malware detected')

    from app.main import app
    app.dependency_overrides[submissions_service.get_scanner] = (
        lambda: RejectingScanner())
    try:
        response = post(client, files=[pdf_part()])
    finally:
        del app.dependency_overrides[submissions_service.get_scanner]
    assert response.status_code == 400
    assert session.scalar(select(func.count()).select_from(Submission)) == 0
    leftovers = [p for p in upload_dir.rglob('*') if p.is_file()]
    assert leftovers == []


def test_submit_cleans_files_when_rollback_fails(client, session, upload_dir,
        monkeypatch):
    """If rollback itself raises, staged/finalized files must still be removed."""
    def failing_commit():
        raise RuntimeError('commit exploded')

    def failing_rollback():
        raise RuntimeError('rollback exploded')

    monkeypatch.setattr(session, 'commit', failing_commit)
    monkeypatch.setattr(session, 'rollback', failing_rollback)
    files = [type('F', (), {'filename': 'laporan.pdf',
        'file': io.BytesIO(pdf_bytes())})()]
    with pytest.raises(RuntimeError):
        submissions_service.intake_submission(session, url=None, context='',
            contact_email=None, files=files, client_net='n' * 64,
            scanner=submissions_service.NoOpScanner())
    leftovers = [p for p in upload_dir.rglob('*') if p.is_file()]
    assert leftovers == []


def make_submission(session, ref='JP-TESTREF0'):
    token = 'receipt-' + uuid4().hex
    submission = Submission(ref=ref,
        receipt_token_hash=hashlib.sha256(token.encode()).hexdigest(),
        submitted_url='https://example.org/p', context='', state='queued',
        client_net_hash='n' * 64, purge_after=NOW + timedelta(days=30),
        created_at=NOW, updated_at=NOW)
    session.add(submission)
    session.flush()
    return submission, token


def test_status_requires_receipt_token(client, session):
    submission, _ = make_submission(session)
    # Header is contract-required: absent -> 422, present-but-wrong -> 401.
    response = client.get(f'/api/v1/submissions/{submission.ref}')
    assert response.status_code == 422
    response = client.get(f'/api/v1/submissions/{submission.ref}',
        headers={'X-Receipt-Token': ''})
    assert response.status_code == 401


def test_status_wrong_token_rejected(client, session):
    submission, _ = make_submission(session)
    response = client.get(f'/api/v1/submissions/{submission.ref}',
        headers={'X-Receipt-Token': 'wrong-token'})
    assert response.status_code == 401


def test_status_unknown_ref_is_404(client, session):
    response = client.get('/api/v1/submissions/JP-NOPE0000',
        headers={'X-Receipt-Token': 'anything'})
    assert response.status_code == 404


def test_status_returns_safe_projection(client, session):
    submission, token = make_submission(session)
    response = client.get(f'/api/v1/submissions/{submission.ref}',
        headers={'X-Receipt-Token': token})
    assert response.status_code == 200
    body = response.json()
    assert body['ref'] == submission.ref
    assert body['state'] == 'queued'
    assert body['status_label'] == 'Dalam antrean'
    assert body['created_at']
    assert body['decision'] is None
    assert body['needs_more_evidence'] is False
    leaked = {'receipt_token_hash', 'client_net_hash', 'submitted_url',
        'contact_email', 'purge_after', 'id'}
    assert leaked.isdisjoint(body)


SCREENING_RESULT = {
    'schema_version': 'screening.v1',
    'outcome': 'complete',
    'submission_text': 'SECRET-SUBMISSION-TEXT',
    'extraction': {'title': 'Beasiswa Unggulan',
        'issuer': 'Kemendikbudristek', 'deadline': '2026-11-30',
        'category': 'scholarship', 'fees': 'gratis',
        'requested_data': ['CV']},
    'discovery': {'query': 'q', 'results': [{'url': 'u'}]},
    'evidence': [{'url': 'https://kemdikbud.go.id/x',
        'final_url': 'https://kemdikbud.go.id/x', 'status': 200,
        'text': 'EVIDENCE-BODY-TEXT', 'origin': 'tavily'}],
    'comparison': {'field_verdicts': {
        'deadline': {'verdict': 'supported', 'quote': 's.d. 30 November'}}},
    'judgments': [{'url': 'https://kemdikbud.go.id/x', 'answers': {
        'official_announcement': {'noul': 0.92},
        'doc_kind': {'choice': 'official_listing'}}}],
    'ai_source_match': True,
    'errors': [{'stage': 'discovery', 'kind': 'unavailable',
        'detail': 'INTERNAL-PROVIDER-DETAIL'}],
    'provider_version': 'INTERNAL',
    'model_version': 'm',
}


def make_run(session, submission, *, state='complete', result=None):
    run = ScreeningRun(submission_id=submission.id, state=state,
        result_json=result, created_at=NOW,
        finished_at=NOW if state == 'complete' else None)
    session.add(run)
    session.commit()
    return run


def test_status_includes_sanitized_screening(client, session):
    submission, token = make_submission(session)
    submission.state = 'review_pending'
    make_run(session, submission, result=SCREENING_RESULT)
    response = client.get(f'/api/v1/submissions/{submission.ref}',
        headers={'X-Receipt-Token': token})
    assert response.status_code == 200
    screening = response.json()['screening']
    assert screening['state'] == 'complete'
    assert screening['outcome'] == 'complete'
    assert screening['extracted']['title'] == 'Beasiswa Unggulan'
    assert screening['field_verdicts']['deadline']['verdict'] == 'supported'
    assert screening['sources'] == [{'url': 'https://kemdikbud.go.id/x',
        'status': 200, 'official': True, 'error': None, 'origin': 'tavily'}]
    assert screening['ai_source_match'] is True
    assert screening['errors'] == [{'stage': 'discovery',
        'kind': 'unavailable'}]
    # No internal material ever reaches the guest payload.
    raw = response.text
    for secret in ('SECRET-SUBMISSION-TEXT', 'EVIDENCE-BODY-TEXT',
            'INTERNAL-PROVIDER-DETAIL', 'INTERNAL',
            'provider_version', 'submission_text', 'judgments'):
        assert secret not in raw


def test_status_screening_exposes_score_and_redacts_qr_urls(client, session):
    submission, token = make_submission(session)
    submission.state = 'review_pending'
    result = {
        **SCREENING_RESULT,
        'extraction': {**SCREENING_RESULT['extraction'],
            'description': 'Program beasiswa.',
            'application_url': 'https://forms.example.org/app?token=secret',
            'source_hint': 'https://example.org/source?key=secret'},
        'evidence': [*SCREENING_RESULT['evidence'], {
            'url': 'https://forms.example.org/app?token=secret',
            'final_url': 'https://forms.example.org/app?token=secret',
            'origin': 'qr_code', 'status': 200, 'text': 'private body'}],
        'confidence': {'score': 83, 'label': 'strong',
            'fields_available': 6, 'fields_checked': 6,
            'fields_supported': 5, 'source_level': 'issuer_website_found',
            'method': 'evidence-support-v1'},
        'site_assessment': {
            'status': 'issuer_website_found',
            'issuer_websites': [{'url': 'https://example.org/source'}],
            'social_sources': [{'url': 'https://instagram.com/p/123'}],
            'third_party_sources': [], 'qr_codes_found': 1},
    }
    make_run(session, submission, result=result)

    response = client.get(f'/api/v1/submissions/{submission.ref}',
        headers={'X-Receipt-Token': token})
    screening = response.json()['screening']

    assert screening['confidence']['score'] == 83
    assert screening['site_assessment'] == {
        'status': 'issuer_website_found', 'issuer_website_candidates': 1,
        'social_sources': 1, 'third_party_sources': 0,
        'unclassified_sources': 0, 'qr_codes_found': 1}
    assert screening['extracted']['description'] == 'Program beasiswa.'
    assert 'application_url' not in screening['extracted']
    assert screening['sources'][-1]['url'] == 'https://forms.example.org/app'
    assert 'token=secret' not in response.text
    assert 'key=secret' not in response.text
    assert 'private body' not in response.text


def test_status_screening_while_processing(client, session):
    submission, token = make_submission(session)
    make_run(session, submission, state='processing')
    response = client.get(f'/api/v1/submissions/{submission.ref}',
        headers={'X-Receipt-Token': token})
    screening = response.json()['screening']
    assert screening['state'] == 'processing'
    assert screening['outcome'] is None
    assert screening['extracted'] is None
    assert screening['sources'] == []


def test_status_without_run_has_null_screening(client, session):
    submission, token = make_submission(session)
    response = client.get(f'/api/v1/submissions/{submission.ref}',
        headers={'X-Receipt-Token': token})
    assert response.json()['screening'] is None


def test_check_endpoint_no_duplicate(client):
    response = client.get('/api/v1/submissions/check',
        params={'url': 'https://belum-ada.id/program'})
    assert response.status_code == 200
    assert response.json()['duplicate'] is False


def test_check_rejects_malformed_url(client):
    response = client.get('/api/v1/submissions/check',
        params={'url': 'notaurl'})
    assert response.status_code == 422


def test_check_matches_pending_submission_normalized(client, session):
    submission, _ = make_submission(session, ref='JP-PENDING01')
    submission.state = 'review_pending'
    submission.submitted_url = (
        'https://Contoh.ID/program/?utm_source=ig#frag')
    session.commit()
    make_run(session, submission, result=SCREENING_RESULT)
    response = client.get('/api/v1/submissions/check',
        params={'url': 'https://contoh.id/program'})
    body = response.json()
    assert body['duplicate'] is True
    assert body['kind'] == 'incoming'
    assert body['ref'] == 'JP-PENDING01'
    assert body['screening']['outcome'] == 'complete'


def test_check_matches_published_listing(client, session, make_entry):
    make_entry('peluang-unik')
    response = client.get('/api/v1/submissions/check',
        params={'url': 'https://EXAMPLE.org/notice/'})
    body = response.json()
    assert body['duplicate'] is True
    assert body['kind'] == 'listing'
    assert body['slug'] == 'peluang-unik'


def test_check_ignores_queued_submission(client, session):
    submission, _ = make_submission(session)
    submission.submitted_url = 'https://baru-saja.id/x'
    session.commit()
    response = client.get('/api/v1/submissions/check',
        params={'url': 'https://baru-saja.id/x'})
    assert response.json()['duplicate'] is False


def test_submit_duplicate_url_conflict(client, session, upload_dir):
    submission, _ = make_submission(session)
    submission.state = 'review_pending'
    submission.submitted_url = 'https://sudah-ada.id/x?utm_medium=x'
    session.commit()
    response = post(client, data={'url': 'https://sudah-ada.id/x'})
    assert response.status_code == 409
    assert response.json()['detail']['error'] == 'duplicate'
    assert response.json()['detail']['kind'] == 'incoming'


def test_status_reports_needs_more_evidence(client, session, official_source):
    submission, token = make_submission(session)
    decision = ModerationDecision(source_evidence_id=official_source.id,
        submission_id=submission.id, actor_id=uuid4(),
        status='needs_more_evidence', decided_at=NOW)
    session.add(decision)
    session.flush()
    response = client.get(f'/api/v1/submissions/{submission.ref}',
        headers={'X-Receipt-Token': token})
    assert response.status_code == 200
    assert response.json()['decision'] == 'needs_more_evidence'
    assert response.json()['needs_more_evidence'] is True


@pytest.mark.parametrize('state,label', [
    ('received', 'Diterima'),
    ('queued', 'Dalam antrean'),
    ('processing', 'Sedang diproses'),
    ('review_pending', 'Menunggu peninjauan moderator'),
    ('published', 'Dipublikasikan'),
    ('closed_unreviewed', 'Ditutup tanpa peninjauan'),
])
def test_status_labels(client, session, state, label):
    submission, token = make_submission(session)
    submission.state = state
    session.flush()
    response = client.get(f'/api/v1/submissions/{submission.ref}',
        headers={'X-Receipt-Token': token})
    assert response.json()['status_label'] == label


def test_submit_rate_limited(client, upload_dir):
    for _ in range(10):
        assert post(client, data={'url': 'https://example.org/x'}).status_code == 202
    assert post(client, data={'url': 'https://example.org/x'}).status_code == 429


def test_status_rate_limited(client, session):
    submission, token = make_submission(session)
    headers = {'X-Receipt-Token': token}
    for _ in range(30):
        assert client.get(f'/api/v1/submissions/{submission.ref}',
            headers=headers).status_code == 200
    assert client.get(f'/api/v1/submissions/{submission.ref}',
        headers=headers).status_code == 429

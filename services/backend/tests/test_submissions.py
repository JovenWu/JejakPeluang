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
from app.security import rate_limiter
from app.services import submissions as submissions_service

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    rate_limiter.reset()
    yield
    rate_limiter.reset()


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
    response = client.get(f'/api/v1/submissions/{submission.ref}')
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

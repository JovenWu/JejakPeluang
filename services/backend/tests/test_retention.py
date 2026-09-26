import hashlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models.intake import ScreeningRun, Submission, Upload
from app.services.retention import (STALE_HOURS_DEFAULT,
    STAGING_MAX_AGE_HOURS_DEFAULT, sweep_expired)

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    target = tmp_path / 'uploads'
    target.mkdir()
    monkeypatch.setenv('UPLOAD_DIR', str(target))
    return target


def aware(value):
    # SQLite returns naive datetimes for DateTime(timezone=True).
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def make_submission(session, *, state='queued', purge_after=None,
        updated_at=NOW, contact_email='guest@example.org'):
    submission = Submission(ref=f'JP-{uuid4().hex[:8].upper()}',
        receipt_token_hash=hashlib.sha256(uuid4().bytes).hexdigest(),
        submitted_url='https://example.org/p', context='ctx',
        contact_email=contact_email, state=state,
        client_net_hash='n' * 64, purge_after=purge_after,
        created_at=NOW, updated_at=updated_at)
    session.add(submission)
    session.commit()
    return submission


def make_upload(session, submission, *, storage_key=None, delete_after=None):
    data = b'%PDF-1.4 fake'
    upload = Upload(submission_id=submission.id,
        storage_key=storage_key or f'{uuid4().hex}.pdf',
        detected_mime='application/pdf', size_bytes=len(data), page_count=1,
        sha256=hashlib.sha256(data).hexdigest(), delete_after=delete_after)
    session.add(upload)
    session.commit()
    return upload


def make_run(session, submission, *, state='complete', result_json=None):
    run = ScreeningRun(submission_id=submission.id, state=state,
        result_json=result_json, created_at=NOW)
    session.add(run)
    session.commit()
    return run


def result_payload():
    return {
        'schema_version': '1',
        'outcome': 'complete',
        'submission_text': 'extracted submitted content',
        'extraction': {'title': 'Beasiswa Uji'},
        'evidence': [
            {'url': 'https://example.org/a',
             'final_url': 'https://example.org/a', 'status': 200,
             'content_type': 'text/html', 'fetched_at': 't',
             'text': 'fetched page text'},
            {'url': 'https://example.org/b', 'status': 404},
        ],
        'comparison': {'field_verdicts': {'title': 'match'}, 'notes': 'n'},
        'judgments': {'official_announcement': {'type': 'noul', 'noul': 0.9}},
        'ai_source_match': True,
        'errors': [],
    }


def test_expired_upload_file_and_row_deleted_fresh_kept(session, upload_dir):
    submission = make_submission(session)
    expired = make_upload(session, submission,
        delete_after=NOW - timedelta(hours=1))
    fresh = make_upload(session, submission,
        delete_after=NOW + timedelta(days=1))
    (upload_dir / expired.storage_key).write_bytes(b'old')
    (upload_dir / fresh.storage_key).write_bytes(b'new')

    counts = sweep_expired(session, now=NOW)

    assert counts['uploads_deleted'] == 1
    assert counts['errors'] == 0
    assert not (upload_dir / expired.storage_key).exists()
    assert (upload_dir / fresh.storage_key).exists()
    remaining = session.scalars(select(Upload)).all()
    assert [u.storage_key for u in remaining] == [fresh.storage_key]


def test_upload_row_deleted_when_file_missing(session, upload_dir):
    submission = make_submission(session)
    make_upload(session, submission, delete_after=NOW - timedelta(hours=1))

    counts = sweep_expired(session, now=NOW)

    assert counts['uploads_deleted'] == 1
    assert session.scalar(select(func.count()).select_from(Upload)) == 0


def test_purged_submission_redacts_pii_keeps_verdicts(session):
    submission = make_submission(session,
        purge_after=NOW - timedelta(hours=1))
    run = make_run(session, submission, result_json=result_payload())

    counts = sweep_expired(session, now=NOW)

    assert counts['submissions_redacted'] == 1
    assert counts['runs_redacted'] == 1
    session.refresh(submission)
    assert submission.contact_email is None
    session.refresh(run)
    result = run.result_json
    assert 'submission_text' not in result
    first, second = result['evidence']
    assert 'text' not in first
    assert first['text_purged'] is True
    assert first['url'] == 'https://example.org/a'
    assert first['status'] == 200
    assert second['url'] == 'https://example.org/b'
    assert result['judgments'] == {
        'official_announcement': {'type': 'noul', 'noul': 0.9}}
    assert result['comparison'] == {
        'field_verdicts': {'title': 'match'}, 'notes': 'n'}
    assert result['extraction'] == {'title': 'Beasiswa Uji'}
    assert result['ai_source_match'] is True


def test_stale_submission_closed_and_run_failed(session):
    old = NOW - timedelta(hours=STALE_HOURS_DEFAULT + 1)
    submission = make_submission(session, state='queued', updated_at=old)
    run = make_run(session, submission, state='processing')

    counts = sweep_expired(session, now=NOW,
        stale_hours=STALE_HOURS_DEFAULT)

    assert counts['stale_closed'] == 1
    session.refresh(submission)
    assert submission.state == 'closed_unreviewed'
    assert aware(submission.updated_at) == NOW
    session.refresh(run)
    assert run.state == 'failed'
    assert run.error == 'stale'
    assert aware(run.finished_at) == NOW


def test_fresh_queued_submission_untouched(session):
    submission = make_submission(session, state='queued', updated_at=NOW)
    run = make_run(session, submission, state='queued')

    counts = sweep_expired(session, now=NOW,
        stale_hours=STALE_HOURS_DEFAULT)

    assert counts['stale_closed'] == 0
    session.refresh(submission)
    assert submission.state == 'queued'
    session.refresh(run)
    assert run.state == 'queued'
    assert run.error is None
    assert run.finished_at is None


def test_staging_orphans_deleted_dirs_untouched(session, upload_dir):
    staging = upload_dir / 'staging'
    staging.mkdir()
    old_file = staging / 'old.part'
    old_file.write_bytes(b'x')
    recent_file = staging / 'new.part'
    recent_file.write_bytes(b'y')
    subdir = staging / 'nested'
    subdir.mkdir()
    inner = subdir / 'inner.part'
    inner.write_bytes(b'z')
    old_ts = (NOW - timedelta(
        hours=STAGING_MAX_AGE_HOURS_DEFAULT + 1)).timestamp()
    os.utime(old_file, (old_ts, old_ts))
    os.utime(subdir, (old_ts, old_ts))
    os.utime(inner, (old_ts, old_ts))
    recent_ts = NOW.timestamp()
    os.utime(recent_file, (recent_ts, recent_ts))

    counts = sweep_expired(session, now=NOW,
        staging_max_age_hours=STAGING_MAX_AGE_HOURS_DEFAULT)

    assert counts['staging_deleted'] == 1
    assert not old_file.exists()
    assert recent_file.exists()
    assert subdir.is_dir()
    assert inner.exists()


def test_second_sweep_is_noop(session, upload_dir):
    submission = make_submission(session,
        purge_after=NOW - timedelta(hours=1))
    make_upload(session, submission, delete_after=NOW - timedelta(hours=1))
    make_run(session, submission, result_json=result_payload())

    first = sweep_expired(session, now=NOW)
    assert first['uploads_deleted'] == 1
    assert first['submissions_redacted'] == 1
    assert first['runs_redacted'] == 1

    second = sweep_expired(session, now=NOW)
    assert second == {'uploads_deleted': 0, 'submissions_redacted': 0,
        'runs_redacted': 0, 'stale_closed': 0, 'staging_deleted': 0,
        'errors': 0}


def test_failing_unit_counts_error_and_sweep_continues(session, upload_dir,
        monkeypatch):
    bad_sub = make_submission(session)
    good_sub = make_submission(session)
    bad = make_upload(session, bad_sub,
        delete_after=NOW - timedelta(hours=1))
    good = make_upload(session, good_sub,
        delete_after=NOW - timedelta(hours=1))
    (upload_dir / bad.storage_key).write_bytes(b'x')
    (upload_dir / good.storage_key).write_bytes(b'y')

    real_unlink = Path.unlink

    def flaky_unlink(self, *args, **kwargs):
        if self.name == bad.storage_key:
            raise OSError('disk error')
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, 'unlink', flaky_unlink)

    counts = sweep_expired(session, now=NOW)

    assert counts['errors'] == 1
    assert counts['uploads_deleted'] == 1
    assert session.get(Upload, bad.id) is not None
    assert session.get(Upload, good.id) is None
    assert (upload_dir / bad.storage_key).exists()
    assert not (upload_dir / good.storage_key).exists()

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models.intake import ScreeningRun, Submission
from test_submissions import SCREENING_RESULT

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)

FEED_URL = '/api/v1/opportunities/incoming'


def make_submission(session, *, state='review_pending',
        created_at=NOW, ref=None, result=SCREENING_RESULT):
    submission = Submission(ref=ref or f'JP-{uuid4().hex[:8].upper()}',
        receipt_token_hash=hashlib.sha256(uuid4().bytes).hexdigest(),
        submitted_url='https://contoh.id/pengumuman',
        context='SECRET-CONTEXT', contact_email='pelapor@example.org',
        state=state, client_net_hash='c' * 64,
        purge_after=NOW + timedelta(days=30), created_at=created_at,
        updated_at=NOW)
    session.add(submission)
    session.flush()
    run = ScreeningRun(submission_id=submission.id,
        state='complete' if state == 'review_pending' else 'queued',
        result_json=result if state == 'review_pending' else None,
        created_at=created_at,
        finished_at=created_at if state == 'review_pending' else None)
    session.add(run)
    session.commit()
    return submission


def test_feed_lists_only_review_pending(client, session):
    pending = make_submission(session)
    for state in ('published', 'rejected', 'queued', 'closed_unreviewed'):
        make_submission(session, state=state)
    response = client.get(FEED_URL)
    assert response.status_code == 200
    body = response.json()
    assert body['total'] == 1
    assert [item['ref'] for item in body['items']] == [pending.ref]


def test_feed_item_is_sanitized(client, session):
    make_submission(session)
    body = client.get(FEED_URL).json()
    item = body['items'][0]
    assert item['verification'] == 'ai_checked'
    assert item['submitted_url'] == 'https://contoh.id/pengumuman'
    assert item['screening']['outcome'] == 'complete'
    assert item['screening']['extracted']['title'] == 'Beasiswa Unggulan'
    assert item['screening']['sources'][0]['official'] is True
    raw = json.dumps(body)
    for secret in ('SECRET-CONTEXT', 'pelapor@example.org',
            'client_net_hash', 'SECRET-SUBMISSION-TEXT',
            'EVIDENCE-BODY-TEXT', 'receipt_token', 'contact_email'):
        assert secret not in raw


def test_feed_newest_first_and_pagination(client, session):
    old = make_submission(session, created_at=NOW - timedelta(days=2))
    new = make_submission(session, created_at=NOW)
    body = client.get(FEED_URL).json()
    assert [item['ref'] for item in body['items']] == [new.ref, old.ref]
    page = client.get(FEED_URL, params={'limit': 1, 'offset': 1}).json()
    assert page['total'] == 2
    assert page['items'][0]['ref'] == old.ref


def test_incoming_detail_returns_projection(client, session):
    pending = make_submission(session)
    response = client.get(f'{FEED_URL}/{pending.ref}')
    assert response.status_code == 200
    item = response.json()
    assert item['ref'] == pending.ref
    assert item['verification'] == 'ai_checked'
    assert item['screening']['field_verdicts']['deadline']['verdict'] == (
        'supported')


def test_incoming_detail_404_for_decided_or_unknown(client, session):
    decided = make_submission(session, state='published')
    assert client.get(f'{FEED_URL}/{decided.ref}').status_code == 404
    assert client.get(f'{FEED_URL}/JP-NOPE0000').status_code == 404


def test_catalogue_items_are_moderator_verified(client, make_entry):
    make_entry('peluang-uji')
    body = client.get('/api/v1/opportunities').json()
    assert body['items'][0]['verification'] == 'moderator_verified'

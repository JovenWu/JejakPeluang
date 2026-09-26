"""End-to-end smoke check for the full service.

Run inside the api container after `compose up --wait` and `alembic upgrade
head`:

    docker compose --env-file infra/.env -f infra/compose.dev.yml exec -T api \
        uv run --no-sync python scripts/e2e_check.py

Walks the real path: guest intake -> outbox -> worker screening with live
providers -> moderator queue/detail -> approve -> public catalogue.
Requires the three provider keys; without them the run still completes with
a degraded outcome and the approval path is exercised the same way.
"""
import sys
import time
from os import environ
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.auth import password_helper  # noqa: E402
from app.db import engine  # noqa: E402
from app.models.auth import User  # noqa: E402

API_BASE = environ.get('API_BASE', 'http://127.0.0.1:8000')
MOD_EMAIL = 'e2e-moderator@jejakpeluang.local'
MOD_PASSWORD = 'e2e-' + uuid4().hex
SUBMIT_URL = environ.get('E2E_SUBMIT_URL',
    'https://beasiswaunggulan.kemdikbud.go.id/')
POLL_TIMEOUT = float(environ.get('E2E_POLL_TIMEOUT', '240'))


def ensure_moderator() -> None:
    # This script writes a moderator account — refuse to run against
    # anything but the disposable E2E database.
    if urlsplit(environ.get('DATABASE_URL', '')).path != '/jejakpeluang_e2e':
        raise RuntimeError(
            'e2e_check requires the isolated jejakpeluang_e2e database')
    with Session(engine()) as session:
        user = session.scalar(select(User).where(
            func.lower(User.email) == MOD_EMAIL))
        hashed = password_helper.hash(MOD_PASSWORD)
        if user is None:
            session.add(User(email=MOD_EMAIL, hashed_password=hashed,
                is_active=True, is_verified=True, role='moderator'))
        else:
            user.hashed_password = hashed
            user.role = 'moderator'
            user.is_active = True
            user.is_verified = True
        session.commit()


def check(name, condition, detail=''):
    status = 'PASS' if condition else 'FAIL'
    print(f'{status} {name} {detail}'.rstrip())
    if not condition:
        raise SystemExit(1)


def main() -> int:
    ensure_moderator()
    client = httpx.Client(base_url=API_BASE, timeout=30,
        headers={'Origin': API_BASE})

    health = client.get('/api/v1/health')
    check('api health', health.status_code == 200, health.text[:80])

    created = client.post('/api/v1/submissions', data={
        'url': SUBMIT_URL,
        'context': 'E2E: Beasiswa Unggulan Kemendikbudristek'})
    check('guest intake', created.status_code == 202, created.text[:160])
    body = created.json()
    ref, token = body['ref'], body['receipt_token']

    deadline = time.time() + POLL_TIMEOUT
    state = ''
    while time.time() < deadline:
        status = client.get(f'/api/v1/submissions/{ref}',
            headers={'X-Receipt-Token': token})
        if status.status_code != 200:
            check('status poll auth', False, status.text[:120])
        state = status.json()['state']
        if state not in ('queued', 'processing', 'received'):
            break
        time.sleep(3)
    check('screening reaches review', state == 'review_pending',
        f'state={state}')

    login = client.post('/api/v1/auth/login',
        data={'username': MOD_EMAIL, 'password': MOD_PASSWORD})
    check('moderator login', login.status_code == 204)

    queue = client.get('/api/v1/moderation/submissions',
        params={'state': 'review_pending', 'limit': 50})
    check('queue listing', queue.status_code == 200, queue.text[:120])
    item = next((i for i in queue.json()['items'] if i['ref'] == ref), None)
    check('submission in queue', item is not None)
    if item is None:
        return 1

    detail = client.get(f"/api/v1/moderation/submissions/{item['id']}")
    check('moderation detail', detail.status_code == 200)
    run = detail.json().get('screening_run')
    check('screening run attached', run is not None
        and run.get('state') == 'complete',
        (run or {}).get('state'))
    outcome = ((run or {}).get('result_json') or {}).get('outcome')
    print(f'  screening outcome={outcome} '
        f"model={run.get('model_version') if run else None}")

    decision = client.post(
        f"/api/v1/moderation/submissions/{item['id']}/decision", json={
            'decision': 'approved',
            'reason': 'e2e approval',
            'fields': {
                'title': 'Beasiswa Unggulan Kemendikbudristek (E2E)',
                'category': 'scholarship',
                'description': 'E2E check listing — moderator approved.',
                'eligibility': 'Mahasiswa S1',
                'issuer_name': 'Kemendikbudristek',
                'trust_basis': 'public_source'}})
    check('approve decision', decision.status_code == 200,
        decision.text[:200])
    slug = decision.json().get('opportunity_slug')
    check('opportunity slug returned', bool(slug), str(slug))

    listing = client.get('/api/v1/opportunities',
        params={'q': 'Beasiswa Unggulan'})
    check('catalogue lists approved opportunity',
        listing.status_code == 200 and any(
            i['slug'] == slug for i in listing.json()['items']))
    print('E2E OK — full intake->screen->review->publish path verified')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

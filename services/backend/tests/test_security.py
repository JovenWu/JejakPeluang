import hashlib
import pytest
from starlette.requests import Request
from app.security import (RATE_LIMIT_SALT, InMemoryRateLimiter,
    client_net_hash, login_attempt_key)


def request_for(host='203.0.113.7', headers=None):
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({'type': 'http', 'method': 'GET', 'path': '/',
        'headers': raw, 'client': (host, 4321)})


def test_client_net_hash_is_salted_sha256():
    request = request_for('203.0.113.7')
    expected = hashlib.sha256(
        f'{RATE_LIMIT_SALT}:203.0.113.7'.encode()).hexdigest()
    assert client_net_hash(request) == expected
    assert client_net_hash(request_for('198.51.100.9')) != expected


def _hashed(ip: str) -> str:
    return hashlib.sha256(f'{RATE_LIMIT_SALT}:{ip}'.encode()).hexdigest()


def test_xff_used_when_peer_is_trusted_proxy(monkeypatch):
    monkeypatch.setenv('TRUSTED_PROXY_CIDRS', '10.0.0.0/8')
    request = request_for('10.0.0.5',
        headers={'X-Forwarded-For': '203.0.113.7'})
    assert client_net_hash(request) == _hashed('203.0.113.7')


def test_xff_ignored_when_peer_untrusted(monkeypatch):
    monkeypatch.setenv('TRUSTED_PROXY_CIDRS', '10.0.0.0/8')
    request = request_for('198.51.100.9',
        headers={'X-Forwarded-For': '203.0.113.7'})
    assert client_net_hash(request) == _hashed('198.51.100.9')


def test_xff_ignored_when_no_trusted_cidrs_configured(monkeypatch):
    monkeypatch.delenv('TRUSTED_PROXY_CIDRS', raising=False)
    request = request_for('10.0.0.5',
        headers={'X-Forwarded-For': '203.0.113.7'})
    assert client_net_hash(request) == _hashed('10.0.0.5')


def test_xff_rightmost_untrusted_hop_wins(monkeypatch):
    # Chain: client 203.0.113.7 -> edge proxy 10.0.0.9 -> traefik 10.0.0.5
    # -> app. The rightmost entry belongs to a trusted hop; the first
    # untrusted-from-the-right is the real client.
    monkeypatch.setenv('TRUSTED_PROXY_CIDRS', '10.0.0.0/8')
    request = request_for('10.0.0.5',
        headers={'X-Forwarded-For': '203.0.113.7, 10.0.0.9'})
    assert client_net_hash(request) == _hashed('203.0.113.7')


def test_xff_client_spoofed_leftmost_entries_not_used(monkeypatch):
    # A client may inject XFF; the trusted proxy still appends the real
    # peer last, so the spoofed value must not win.
    monkeypatch.setenv('TRUSTED_PROXY_CIDRS', '10.0.0.0/8')
    request = request_for('10.0.0.5',
        headers={'X-Forwarded-For': '1.2.3.4, 203.0.113.7'})
    assert client_net_hash(request) == _hashed('203.0.113.7')


def test_xff_absent_or_garbage_falls_back_to_peer(monkeypatch):
    monkeypatch.setenv('TRUSTED_PROXY_CIDRS', '10.0.0.0/8')
    request = request_for('10.0.0.5')
    assert client_net_hash(request) == _hashed('10.0.0.5')
    garbage = request_for('10.0.0.5',
        headers={'X-Forwarded-For': 'not-an-ip, , '})
    assert client_net_hash(garbage) == _hashed('10.0.0.5')


def test_invalid_trusted_cidr_entry_ignored(monkeypatch):
    monkeypatch.setenv('TRUSTED_PROXY_CIDRS', 'bogus,10.0.0.0/8')
    trusted = request_for('10.0.0.5',
        headers={'X-Forwarded-For': '203.0.113.7'})
    assert client_net_hash(trusted) == _hashed('203.0.113.7')
    untrusted = request_for('198.51.100.9',
        headers={'X-Forwarded-For': '203.0.113.7'})
    assert client_net_hash(untrusted) == _hashed('198.51.100.9')


def test_forwarded_clients_get_distinct_rate_limit_identities(monkeypatch):
    monkeypatch.setenv('TRUSTED_PROXY_CIDRS', '10.0.0.0/8')
    a = request_for('10.0.0.5', headers={'X-Forwarded-For': '203.0.113.7'})
    b = request_for('10.0.0.5', headers={'X-Forwarded-For': '198.51.100.9'})
    assert client_net_hash(a) != client_net_hash(b)
    assert (login_attempt_key(a, 'm@example.org')
        != login_attempt_key(b, 'm@example.org'))


def test_in_memory_rate_limiter_enforces_limit():
    limiter = InMemoryRateLimiter()
    for _ in range(3):
        assert limiter.check('k', limit=3, window_seconds=60)
    assert not limiter.check('k', limit=3, window_seconds=60)


def test_in_memory_rate_limiter_resets_after_window():
    now = [1000.0]
    limiter = InMemoryRateLimiter(clock=lambda: now[0])
    assert limiter.check('k', limit=1, window_seconds=60)
    assert not limiter.check('k', limit=1, window_seconds=60)
    now[0] += 61
    assert limiter.check('k', limit=1, window_seconds=60)


def test_in_memory_rate_limiter_keys_are_independent():
    limiter = InMemoryRateLimiter()
    assert limiter.check('a', limit=1, window_seconds=60)
    assert limiter.check('b', limit=1, window_seconds=60)
    assert not limiter.check('a', limit=1, window_seconds=60)


def test_in_memory_rate_limiter_evicts_stale_keys():
    now = [0.0]
    limiter = InMemoryRateLimiter(clock=lambda: now[0], max_buckets=2)
    limiter.check('old', limit=1, window_seconds=60)
    now[0] = 120.0
    limiter.check('a', limit=1, window_seconds=60)
    limiter.check('b', limit=1, window_seconds=60)
    limiter.check('c', limit=1, window_seconds=60)
    assert 'old' not in limiter._buckets
    assert set(limiter._buckets) == {'a', 'b', 'c'}


@pytest.fixture
def authed_client(client, make_user, auth_cookie):
    user = make_user('csrf@example.org')
    client.cookies.set('jp_auth', auth_cookie(user))
    return client


def test_csrf_blocks_cookie_post_without_origin(authed_client):
    assert authed_client.post('/api/v1/auth/logout').status_code == 403


def test_csrf_blocks_cookie_post_with_foreign_origin(authed_client):
    response = authed_client.post('/api/v1/auth/logout',
        headers={'Origin': 'https://evil.example'})
    assert response.status_code == 403


def test_csrf_blocks_cookie_post_with_malformed_origin(authed_client):
    response = authed_client.post('/api/v1/auth/logout',
        headers={'Origin': 'http://['})
    assert response.status_code == 403


def test_csrf_allows_cookie_post_with_matching_origin(authed_client):
    response = authed_client.post('/api/v1/auth/logout',
        headers={'Origin': 'http://testserver'})
    assert response.status_code == 204


def test_csrf_allows_cookie_post_with_matching_referer(authed_client):
    response = authed_client.post('/api/v1/auth/logout',
        headers={'Referer': 'http://testserver/moderation'})
    assert response.status_code == 204


def test_csrf_ignores_requests_without_auth_cookie(client):
    response = client.post('/api/v1/auth/login',
        data={'username': 'nobody@example.org', 'password': 'x'})
    assert response.status_code == 400


def test_csrf_ignores_safe_methods(authed_client):
    assert authed_client.get('/api/v1/users/me').status_code == 200

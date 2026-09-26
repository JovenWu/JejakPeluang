import hashlib
import pytest
from starlette.requests import Request
from app.security import (RATE_LIMIT_SALT, InMemoryRateLimiter,
    client_net_hash)


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

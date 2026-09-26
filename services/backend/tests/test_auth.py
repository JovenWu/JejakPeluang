import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from app.auth import require_moderator
from app.db import get_session
from app.models.auth import User
from app.security import rate_limiter


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    rate_limiter.reset()
    yield
    rate_limiter.reset()


def login(client, email, password='correct-horse'):
    return client.post('/api/v1/auth/login',
        data={'username': email, 'password': password})


def test_login_sets_httponly_cookie(client, make_user):
    make_user('mod@example.org')
    response = login(client, 'mod@example.org')
    assert response.status_code == 204
    assert response.cookies.get('jp_auth')
    set_cookie = response.headers['set-cookie'].lower()
    assert 'httponly' in set_cookie
    assert 'samesite=lax' in set_cookie


def test_login_wrong_password_rejected(client, make_user):
    make_user('mod@example.org')
    response = login(client, 'mod@example.org', 'wrong-password')
    assert response.status_code == 400


def test_login_unknown_email_rejected(client):
    response = login(client, 'ghost@example.org')
    assert response.status_code == 400


def test_login_rate_limited_after_five_attempts(client, make_user):
    make_user('limited@example.org')
    for _ in range(5):
        response = login(client, 'limited@example.org', 'wrong-password')
        assert response.status_code == 400
    response = login(client, 'limited@example.org')
    assert response.status_code == 429


def test_users_me_requires_auth(client):
    assert client.get('/api/v1/users/me').status_code == 401


def test_users_me_returns_current_user(client, make_user):
    make_user('mod@example.org')
    login(client, 'mod@example.org')
    response = client.get('/api/v1/users/me')
    assert response.status_code == 200
    body = response.json()
    assert body['email'] == 'mod@example.org'
    assert body['role'] == 'moderator'


def test_logout_revokes_token(client, make_user):
    make_user('mod@example.org')
    login(client, 'mod@example.org')
    response = client.post('/api/v1/auth/logout',
        headers={'Origin': 'http://testserver'})
    assert response.status_code == 204
    assert client.get('/api/v1/users/me').status_code == 401


def test_registration_endpoint_absent(client):
    response = client.post('/api/v1/auth/register',
        json={'email': 'new@example.org', 'password': 'x' * 12})
    assert response.status_code == 404


probe_app = FastAPI()


@probe_app.get('/mod-probe')
def mod_probe(user: User = Depends(require_moderator)):
    return {'email': user.email}


@pytest.fixture
def probe_client(session):
    def override():
        yield session
    probe_app.dependency_overrides[get_session] = override
    with TestClient(probe_app) as c:
        yield c
    probe_app.dependency_overrides.clear()


def test_require_moderator_unauthenticated(probe_client):
    assert probe_client.get('/mod-probe').status_code == 401


def test_require_moderator_denies_non_moderator(probe_client, make_user, auth_cookie):
    user = make_user('viewer@example.org', role='viewer')
    probe_client.cookies.set('jp_auth', auth_cookie(user))
    assert probe_client.get('/mod-probe').status_code == 403


def test_require_moderator_allows_moderator(probe_client, make_user, auth_cookie):
    user = make_user('mod@example.org')
    probe_client.cookies.set('jp_auth', auth_cookie(user))
    response = probe_client.get('/mod-probe')
    assert response.status_code == 200
    assert response.json()['email'] == 'mod@example.org'

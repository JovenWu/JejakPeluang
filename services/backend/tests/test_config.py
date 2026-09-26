import pytest

from app.config import assert_production_config
from app.security import RedisRateLimiter
from app.services.outbox import make_publisher


def _prod(monkeypatch, **env):
    monkeypatch.setenv('APP_ENV', 'production')
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def test_production_rejects_default_secrets(monkeypatch):
    _prod(monkeypatch, AUTH_SECRET='jp-dev-auth-secret-change-me',
        RATE_LIMIT_SALT='jp-dev-rate-limit-salt', COOKIE_SECURE='true',
        REDIS_URL='redis://x')
    with pytest.raises(RuntimeError, match='AUTH_SECRET'):
        assert_production_config()


def test_production_requires_cookie_secure(monkeypatch):
    _prod(monkeypatch, AUTH_SECRET='s3cret', RATE_LIMIT_SALT='pepper',
        COOKIE_SECURE='false', REDIS_URL='redis://x')
    with pytest.raises(RuntimeError, match='COOKIE_SECURE'):
        assert_production_config()


def test_production_requires_redis_url_for_broker(monkeypatch):
    _prod(monkeypatch, AUTH_SECRET='s3cret', RATE_LIMIT_SALT='pepper',
        COOKIE_SECURE='true', JOB_BROKER='redis')
    monkeypatch.delenv('REDIS_URL', raising=False)
    with pytest.raises(RuntimeError, match='REDIS_URL'):
        assert_production_config()


def test_production_ok_with_real_values(monkeypatch):
    _prod(monkeypatch, AUTH_SECRET='s3cret', RATE_LIMIT_SALT='pepper',
        COOKIE_SECURE='true', REDIS_URL='redis://x', JOB_BROKER='redis')
    assert_production_config()


def test_development_allows_defaults(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.delenv('REDIS_URL', raising=False)
    assert_production_config()


def test_unset_env_is_development(monkeypatch):
    monkeypatch.delenv('APP_ENV', raising=False)
    assert_production_config()


class FakeRedisClient:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def incr(self, key):
        if self.fail:
            raise ConnectionError('down')
        self.calls.append(('incr', key))
        return sum(1 for op, k in self.calls if op == 'incr' and k == key)

    def expire(self, key, ttl):
        self.calls.append(('expire', key))


def test_redis_rate_limiter_enforces_window():
    client = FakeRedisClient()
    limiter = RedisRateLimiter(client=client, clock=lambda: 1000.0)
    assert limiter.check('k', 2, 60) is True
    assert limiter.check('k', 2, 60) is True
    assert limiter.check('k', 2, 60) is False
    keys = [k for op, k in client.calls if op == 'incr']
    assert all(k.startswith('jp:rl:k:') for k in keys)


def test_redis_rate_limiter_new_window_resets():
    t = {'now': 1000.0}
    client = FakeRedisClient()
    limiter = RedisRateLimiter(client=client, clock=lambda: t['now'])
    limiter.check('k', 1, 60)
    assert limiter.check('k', 1, 60) is False
    t['now'] = 2000.0
    assert limiter.check('k', 1, 60) is True


def test_redis_rate_limiter_fails_open_when_down(caplog):
    limiter = RedisRateLimiter(client=FakeRedisClient(fail=True))
    assert limiter.check('k', 1, 60) is True


def test_get_rate_limiter_is_cached_singleton():
    from app import security
    a = security.get_rate_limiter()
    assert security.get_rate_limiter() is a
    assert a is security.rate_limiter


def test_get_rate_limiter_redis_backend_cached(monkeypatch):
    monkeypatch.setenv('RATE_LIMITER', 'redis')
    monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379/0')
    from app import security
    a = security.get_rate_limiter()
    assert isinstance(a, security.RedisRateLimiter)
    assert security.get_rate_limiter() is a


def test_make_publisher_defaults_to_logging(monkeypatch):
    monkeypatch.delenv('REDIS_URL', raising=False)
    monkeypatch.delenv('JOB_BROKER', raising=False)
    from app.services.outbox import LoggingPublisher
    assert isinstance(make_publisher(), LoggingPublisher)


def test_make_publisher_redis_requires_url(monkeypatch):
    monkeypatch.setenv('JOB_BROKER', 'redis')
    monkeypatch.delenv('REDIS_URL', raising=False)
    with pytest.raises(RuntimeError, match='REDIS_URL'):
        make_publisher()


def test_make_publisher_uses_redis_url(monkeypatch):
    monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379/0')
    from app.services.outbox import RedisPublisher
    publisher = make_publisher()
    assert isinstance(publisher, RedisPublisher)

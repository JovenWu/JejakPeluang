import hashlib
import ipaddress
import logging
import time
from http.cookies import SimpleCookie
from os import environ
from typing import Protocol
from urllib.parse import urlsplit

from fastapi import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

RATE_LIMIT_SALT = environ.get('RATE_LIMIT_SALT', 'jp-dev-rate-limit-salt')
AUTH_COOKIE_NAME = 'jp_auth'
UNSAFE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}


class RateLimiter(Protocol):
    """Fixed-window rate limit check. Returns True while under the limit.

    Implementations slot in via get_rate_limiter; a RedisRateLimiter backed by
    INCR + EXPIRE can replace InMemoryRateLimiter without touching call sites.
    """

    def check(self, key: str, limit: int, window_seconds: int) -> bool:
        ...


class InMemoryRateLimiter:
    """Process-local fixed-window limiter; not shared across workers.

    Buckets map key -> (window_index, count, expires_at_epoch). When the map
    grows past max_buckets, expired entries are evicted on the next check so
    attacker-controlled keys cannot grow memory without bound.
    """

    def __init__(self, clock=time.time, max_buckets: int = 10_000):
        self._clock = clock
        self._max_buckets = max_buckets
        self._buckets: dict[str, tuple[int, int, float]] = {}

    def check(self, key: str, limit: int, window_seconds: int) -> bool:
        now = self._clock()
        window = int(now // window_seconds)
        if len(self._buckets) > self._max_buckets:
            self._evict_expired(now)
        bucket = self._buckets.get(key)
        if bucket is None or bucket[0] != window:
            self._buckets[key] = (window, 1, (window + 1) * window_seconds)
            return True
        if bucket[1] >= limit:
            return False
        self._buckets[key] = (window, bucket[1] + 1, bucket[2])
        return True

    def _evict_expired(self, now: float) -> None:
        self._buckets = {key: bucket for key, bucket in self._buckets.items()
            if bucket[2] > now}

    def reset(self) -> None:
        self._buckets.clear()


class RedisRateLimiter:
    """Fixed-window limiter shared across processes via Redis INCR/EXPIRE.

    Fail-open by design: if Redis is unreachable the request is allowed and
    a warning is logged — rate limiting is defense-in-depth, not worth an
    outage. Set RATE_LIMITER=redis with REDIS_URL to enable.
    """

    def __init__(self, redis_url: str | None = None, client=None,
            clock=time.time):
        if client is not None:
            self._client = client
        else:
            import redis as redis_lib
            self._client = redis_lib.Redis.from_url(redis_url)
        self._clock = clock
        self._failures = 0

    def check(self, key: str, limit: int, window_seconds: int) -> bool:
        window = int(self._clock() // window_seconds)
        rkey = f'jp:rl:{key}:{window}'
        try:
            count = self._client.incr(rkey)
            if count == 1:
                self._client.expire(rkey, window_seconds * 2)
        except Exception:
            self._failures += 1
            if self._failures == 1 or self._failures % 100 == 0:
                logger.warning('rate limiter backend unavailable '
                    '(fail-open); failures=%d', self._failures)
            return True
        return count <= limit


rate_limiter = InMemoryRateLimiter()


def make_rate_limiter() -> RateLimiter:
    """RATE_LIMITER=redis selects the shared limiter; default is in-memory."""
    if environ.get('RATE_LIMITER') == 'redis':
        redis_url = environ.get('REDIS_URL')
        if not redis_url:
            raise RuntimeError('RATE_LIMITER=redis requires REDIS_URL')
        return RedisRateLimiter(redis_url)
    return rate_limiter


_configured_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """The configured limiter as a process-wide singleton — Redis-backed
    limiters hold a client+pool that must not be rebuilt per request."""
    global _configured_limiter
    if _configured_limiter is None:
        _configured_limiter = make_rate_limiter()
    return _configured_limiter


def _trusted_proxy_cidrs() -> list:
    raw = environ.get('TRUSTED_PROXY_CIDRS', '')
    nets = []
    for part in raw.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            nets.append(ipaddress.ip_network(part))
        except ValueError:
            logger.warning('ignoring invalid TRUSTED_PROXY_CIDRS entry %r',
                part)
    return nets


def _client_ip(request: Request) -> str:
    """Socket peer, or the rightmost untrusted X-Forwarded-For entry when the
    peer is a configured trusted proxy (TRUSTED_PROXY_CIDRS). Client-supplied
    XFF entries to the left are never trusted; hops that are themselves
    trusted proxies or unparseable are skipped."""
    peer = request.client.host if request.client else 'unknown'
    try:
        peer_addr = ipaddress.ip_address(peer)
    except ValueError:
        return peer
    nets = _trusted_proxy_cidrs()
    if not nets or not any(peer_addr in net for net in nets):
        return peer
    forwarded = request.headers.get('x-forwarded-for', '')
    for hop in reversed(forwarded.split(',')):
        hop = hop.strip()
        try:
            hop_addr = ipaddress.ip_address(hop)
        except ValueError:
            continue
        if any(hop_addr in net for net in nets):
            continue
        return str(hop_addr)
    return peer


def client_net_hash(request: Request) -> str:
    return hashlib.sha256(
        f'{RATE_LIMIT_SALT}:{_client_ip(request)}'.encode()).hexdigest()


def login_attempt_key(request: Request, email: str) -> str:
    return hashlib.sha256(
        f'{RATE_LIMIT_SALT}:{email.strip().lower()}:'
        f'{_client_ip(request)}'.encode()).hexdigest()


class CsrfOriginMiddleware:
    """Block unsafe requests carrying the auth cookie without a same-host origin.

    A request with the session cookie must present an Origin or Referer whose
    host matches Host/X-Forwarded-Host, proving the browser sent it from this
    site. Cookie-free requests (e.g. X-Receipt-Token guest routes) are exempt.
    """

    def __init__(self, app: ASGIApp, cookie_name: str = AUTH_COOKIE_NAME):
        self.app = app
        self.cookie_name = cookie_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http' or self._allowed(scope):
            await self.app(scope, receive, send)
            return
        response = JSONResponse({'detail': 'CSRF check failed'}, status_code=403)
        await response(scope, receive, send)

    def _allowed(self, scope: Scope) -> bool:
        if scope['method'] not in UNSAFE_METHODS:
            return True
        headers = {key.decode('latin-1'): value.decode('latin-1')
            for key, value in scope['headers']}
        if self.cookie_name not in self._cookies(headers.get('cookie', '')):
            return True
        host = headers.get('x-forwarded-host', headers.get('host', ''))
        host = host.split(',', 1)[0].split(':', 1)[0].strip().lower()
        if not host:
            return False
        source = headers.get('origin') or headers.get('referer')
        if not source:
            return False
        try:
            source_host = urlsplit(source).hostname
        except ValueError:
            return False
        return source_host is not None and source_host.lower() == host

    @staticmethod
    def _cookies(header: str) -> set[str]:
        jar = SimpleCookie()
        jar.load(header)
        return set(jar.keys())

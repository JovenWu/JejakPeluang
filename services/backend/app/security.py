import hashlib
import time
from http.cookies import SimpleCookie
from os import environ
from typing import Protocol
from urllib.parse import urlsplit

from fastapi import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

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
    """Process-local fixed-window limiter; not shared across workers."""

    def __init__(self, clock=time.time):
        self._clock = clock
        self._buckets: dict[str, tuple[int, int]] = {}

    def check(self, key: str, limit: int, window_seconds: int) -> bool:
        window = int(self._clock() // window_seconds)
        bucket = self._buckets.get(key)
        if bucket is None or bucket[0] != window:
            self._buckets[key] = (window, 1)
            return True
        if bucket[1] >= limit:
            return False
        self._buckets[key] = (window, bucket[1] + 1)
        return True

    def reset(self) -> None:
        self._buckets.clear()


rate_limiter = InMemoryRateLimiter()


def get_rate_limiter() -> RateLimiter:
    return rate_limiter


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else 'unknown'


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
        source_host = urlsplit(source).hostname
        return source_host is not None and source_host.lower() == host

    @staticmethod
    def _cookies(header: str) -> set[str]:
        jar = SimpleCookie()
        jar.load(header)
        return set(jar.keys())

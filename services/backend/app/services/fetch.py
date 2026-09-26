"""SSRF-hardened fetcher for the screening pipeline.

Every fetch resolves the host itself, requires ALL candidate addresses to
be public, then pins the connection: the request URL carries the validated
IP literal while an explicit ``Host`` header (and, for https, the
``sni_hostname`` request extension) preserves the original hostname.
Verified against httpx 0.28.1 — both reach the wire — so no second DNS
lookup happens at connect time and the rebinding window stays closed.
"""

import ipaddress
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import SplitResult, urljoin, urlsplit

import httpx

MAX_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 5
DEFAULT_TIMEOUT_SECONDS = 10.0
USER_AGENT = 'JejakPeluang-Screening/1.0'

_ACCEPT = ('text/html,application/xhtml+xml,application/pdf,'
    'text/plain;q=0.9,*/*;q=0.5')
_ALLOWED_PORTS = (None, 80, 443)
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_NAT64 = ipaddress.ip_network('64:ff9b::/96')

Resolver = Callable[[str, int], list[str]]


class FetchError(Exception):
    """Fetch rejection; .kind is one of 'invalid_url', 'forbidden_host',
    'dns_blocked', 'connect_failed', 'timeout', 'too_large', 'http_error',
    'too_many_redirects'."""

    def __init__(self, kind: str, detail: str = '',
            *, status: int | None = None):
        super().__init__(detail or kind)
        self.kind = kind
        self.detail = detail
        self.status = status


@dataclass
class FetchResult:
    requested_url: str
    final_url: str
    status: int
    content_type: str | None
    content: bytes
    fetched_at: datetime


def _default_resolver(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    ips: list[str] = []
    for info in infos:
        ip = info[4][0]
        if ip not in ips:
            ips.append(ip)
    return ips


def _ip_literal(host: str) -> str | None:
    """Canonical IP when host is already a literal — inet_aton also catches
    hex/octal/integer IPv4 encodings such as ``0x7f.0.0.1`` or
    ``2130706433`` that resolvers would treat as addresses."""
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        pass
    try:
        return str(ipaddress.ip_address(socket.inet_aton(host)))
    except OSError:
        return None


def _is_public(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if isinstance(addr, ipaddress.IPv6Address):
        # Unwrap embedded IPv4 so mapped/transition forms of private IPv4
        # addresses cannot smuggle past the is_global check.
        embedded = addr.ipv4_mapped or addr.sixtofour
        if addr.teredo is not None:
            embedded = addr.teredo[1]
        if embedded is None and addr in _NAT64:
            embedded = ipaddress.ip_address(addr.packed[-4:])
        if embedded is not None:
            addr = embedded
    return addr.is_global


def _parse_url(url: str) -> SplitResult:
    try:
        parts = urlsplit(url)
    except ValueError:
        raise FetchError('invalid_url', f'malformed url: {url}')
    if parts.scheme not in ('http', 'https'):
        raise FetchError('invalid_url', f'unsupported scheme: {url}')
    if parts.username is not None or parts.password is not None:
        raise FetchError('invalid_url', f'credentials in url: {url}')
    try:
        port = parts.port
    except ValueError:
        raise FetchError('invalid_url', f'invalid port: {url}')
    if port not in _ALLOWED_PORTS:
        raise FetchError('invalid_url', f'invalid port: {url}')
    if not parts.hostname:
        raise FetchError('invalid_url', f'missing host: {url}')
    return parts


def _pinned_ip(parts: SplitResult, resolver: Resolver) -> str:
    """Resolve and validate; return the public IP literal to connect to.
    Every candidate must be public — a single private address in the set
    rejects the host outright."""
    host = parts.hostname
    port = parts.port or (443 if parts.scheme == 'https' else 80)
    literal = _ip_literal(host)
    if literal is not None:
        ips = [literal]
    else:
        try:
            ips = resolver(host, port)
        except socket.gaierror as exc:
            raise FetchError('dns_blocked',
                f'cannot resolve {host}') from exc
        except UnicodeError as exc:
            raise FetchError('invalid_url', f'invalid host: {host}') from exc
        if not ips:
            raise FetchError('dns_blocked', f'cannot resolve {host}')
    for ip in ips:
        if not _is_public(ip):
            raise FetchError('forbidden_host',
                f'{host} resolves to a non-public address')
    return ips[0]


def _pinned_url(parts: SplitResult, ip: str) -> str:
    netloc = f'[{ip}]' if ':' in ip else ip
    if parts.port is not None:
        netloc = f'{netloc}:{parts.port}'
    path = parts.path or '/'
    if parts.query:
        path = f'{path}?{parts.query}'
    return f'{parts.scheme}://{netloc}{path}'


def _host_header(parts: SplitResult) -> str:
    host = parts.hostname
    if ':' in host:
        host = f'[{host}]'
    default_port = 443 if parts.scheme == 'https' else 80
    if parts.port not in (None, default_port):
        host = f'{host}:{parts.port}'
    return host


def _send(client: httpx.Client, request: httpx.Request) -> httpx.Response:
    try:
        return client.send(request, stream=True)
    except httpx.TimeoutException as exc:
        raise FetchError('timeout', str(exc) or 'timed out') from exc
    except httpx.HTTPError as exc:
        raise FetchError('connect_failed',
            str(exc) or type(exc).__name__) from exc


def _read_body(response: httpx.Response, max_bytes: int, deadline: float,
        clock=time.monotonic) -> bytes:
    chunks: list[bytes] = []
    size = 0
    try:
        for chunk in response.iter_bytes():
            # httpx timeouts bound each socket read, not total elapsed — a
            # trickling server would otherwise hold the worker past the
            # per-page budget.
            if clock() > deadline:
                raise FetchError('timeout',
                    'response body exceeded the fetch deadline')
            size += len(chunk)
            if size > max_bytes:
                raise FetchError('too_large',
                    f'response body exceeds {max_bytes} bytes')
            chunks.append(chunk)
    except httpx.TimeoutException as exc:
        raise FetchError('timeout', str(exc) or 'timed out') from exc
    except httpx.HTTPError as exc:
        raise FetchError('connect_failed',
            str(exc) or type(exc).__name__) from exc
    finally:
        response.close()
    return b''.join(chunks)


def fetch(url: str, *, resolver: Resolver | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_redirects: int = MAX_REDIRECTS,
        max_bytes: int = MAX_BYTES,
        clock=time.monotonic) -> FetchResult:
    resolve = resolver or _default_resolver
    deadline = clock() + timeout
    client = httpx.Client(
        transport=transport or httpx.HTTPTransport(),
        follow_redirects=False,
        timeout=httpx.Timeout(timeout, connect=min(timeout, 5.0)),
        headers={'User-Agent': USER_AGENT, 'Accept': _ACCEPT})
    try:
        current = url
        visited = {current}
        redirects = 0
        while True:
            parts = _parse_url(current)
            ip = _pinned_ip(parts, resolve)
            # Redirect responses may carry Set-Cookie; the jar must stay
            # empty so no hop can leak credentials to the next.
            client.cookies.clear()
            request = client.build_request('GET', _pinned_url(parts, ip),
                headers={'Host': _host_header(parts)},
                extensions={'sni_hostname': parts.hostname}
                    if parts.scheme == 'https' else None)
            response = _send(client, request)
            location = response.headers.get('location')
            if response.status_code in _REDIRECT_STATUSES and location:
                response.close()
                redirects += 1
                target = urljoin(current, location)
                if redirects > max_redirects or target in visited:
                    raise FetchError('too_many_redirects',
                        f'redirect limit or loop at {target}')
                visited.add(target)
                current = target
                continue
            if not 200 <= response.status_code < 300:
                response.close()
                raise FetchError('http_error',
                    f'{current} returned status {response.status_code}',
                    status=response.status_code)
            content_type = response.headers.get('content-type')
            if content_type is not None:
                content_type = (content_type.split(';', 1)[0].strip().lower()
                    or None)
            return FetchResult(requested_url=url, final_url=current,
                status=response.status_code, content_type=content_type,
                content=_read_body(response, max_bytes, deadline,
                    clock=clock),
                fetched_at=datetime.now(timezone.utc))
    finally:
        client.close()

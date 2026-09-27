"""Headless-browser rendering for client-side (JavaScript-only) pages.

Runs inside the isolated ``renderer`` service, never in the API or worker.
The browser is given no network of its own: every request it makes —
document, scripts, XHR — is intercepted and served through the
SSRF-hardened :func:`app.services.fetch.fetch` (public IPs only, pinned
connections, size caps). Chromium is also pointed at a dead proxy, so any
traffic that could escape interception (WebSockets, WebRTC, prefetch)
fails instead of reaching the network directly.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.services.fetch import USER_AGENT, FetchError, FetchResult, fetch

RENDER_TIMEOUT_SECONDS = 20.0
SUBREQUEST_TIMEOUT_SECONDS = 6.0
MAX_SUBREQUESTS = 80
MAX_SUBREQUEST_BYTES = 6 * 1024 * 1024
MAX_TOTAL_BYTES = 24 * 1024 * 1024
MAX_HTML_CHARS = 2 * 1024 * 1024
# Nothing renders text from these, so skip them to save fetch budget.
_SKIPPED_RESOURCES = frozenset({'image', 'media', 'font', 'manifest',
    'texttrack', 'eventsource', 'websocket', 'ping', 'other'})
_DEAD_PROXY = 'http://127.0.0.1:9'
_BROWSER_ARGS = [
    f'--proxy-server={_DEAD_PROXY}',
    # Chromium bypasses proxies for loopback by default; remove that bypass.
    '--proxy-bypass-list=<-loopback>',
    '--force-webrtc-ip-handling-policy=disable_non_proxied_udp',
    '--disable-background-networking',
    '--disable-dev-shm-usage',
    '--no-first-run',
]

Fetcher = Callable[..., FetchResult]


class RenderError(Exception):
    def __init__(self, kind: str, detail: str = ''):
        super().__init__(detail or kind)
        self.kind = kind
        self.detail = detail


@dataclass
class _Budget:
    deadline: float
    clock: Callable[[], float]
    requests: int = 0
    total_bytes: int = 0
    document_status: int | None = None

    def remaining(self) -> float:
        return self.deadline - self.clock()


def _handler(fetcher: Fetcher, budget: _Budget) -> Callable[[Any, Any], None]:
    def handle(route: Any, request: Any) -> None:
        if (request.resource_type in _SKIPPED_RESOURCES
                or request.method not in ('GET', 'HEAD')
                or budget.requests >= MAX_SUBREQUESTS
                or budget.total_bytes >= MAX_TOTAL_BYTES
                or budget.remaining() <= 0.5):
            route.abort()
            return
        budget.requests += 1
        try:
            result = fetcher(request.url,
                timeout=min(SUBREQUEST_TIMEOUT_SECONDS, budget.remaining()),
                max_bytes=MAX_SUBREQUEST_BYTES)
        except FetchError as exc:
            if exc.status is not None:
                route.fulfill(status=exc.status, body=b'')
            else:
                route.abort()
            return
        budget.total_bytes += len(result.content)
        navigation = request.is_navigation_request()
        # fetch() follows redirects itself; replay the final hop so the
        # page's relative URLs resolve against the real location.
        if navigation and result.final_url != request.url:
            route.fulfill(status=302, headers={'location': result.final_url},
                body=b'')
            return
        if navigation and request.frame.parent_frame is None:
            budget.document_status = result.status
        route.fulfill(status=result.status, body=result.content, headers={
            'content-type': result.content_type or 'application/octet-stream',
            'access-control-allow-origin': '*',
        })
    return handle


def render(url: str, *, fetcher: Fetcher = fetch,
        timeout: float = RENDER_TIMEOUT_SECONDS,
        clock: Callable[[], float] = time.monotonic) -> FetchResult:
    """Load ``url`` in headless Chromium and return the rendered DOM."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright

    # Validate the entry URL (scheme, port, public DNS) before a browser
    # starts; every later request is re-validated by the fetcher.
    fetcher(url, timeout=min(SUBREQUEST_TIMEOUT_SECONDS, timeout),
        max_bytes=MAX_SUBREQUEST_BYTES)
    budget = _Budget(deadline=clock() + timeout, clock=clock)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(args=_BROWSER_ARGS)
            try:
                context = browser.new_context(user_agent=USER_AGENT,
                    locale='id-ID', service_workers='block',
                    accept_downloads=False, java_script_enabled=True)
                page = context.new_page()
                page.route('**/*', _handler(fetcher, budget))
                page.goto(url, wait_until='domcontentloaded',
                    timeout=max(1.0, budget.remaining()) * 1000)
                try:
                    page.wait_for_load_state('networkidle',
                        timeout=max(0.5, budget.remaining() - 1.0) * 1000)
                except PlaywrightTimeout:
                    pass  # long-polling pages never idle; use what rendered
                html = page.content()[:MAX_HTML_CHARS]
                final_url = page.url
            finally:
                browser.close()
    except PlaywrightTimeout as exc:
        raise RenderError('render_timeout', str(exc)) from exc
    except PlaywrightError as exc:
        raise RenderError('render_failed', str(exc)) from exc
    return FetchResult(requested_url=url, final_url=final_url,
        status=budget.document_status or 200, content_type='text/html',
        content=html.encode('utf-8'), fetched_at=datetime.now(timezone.utc),
        rendered=True)

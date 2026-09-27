import json
import time
from datetime import datetime, timezone

import httpx

from app.services.fetch import FetchError, FetchResult
from app.services.render import MAX_SUBREQUESTS, _Budget, _handler
from app.services.render_client import needs_rendering, with_rendering
from app.services.screening import _fetch_evidence

SHELL = (b'<!doctype html><html><head><title>App</title></head><body>'
    b'<noscript>You need to enable JavaScript to run this app.</noscript>'
    b'<div id="root"></div></body></html>')
RENDERED = ('<html><body><main><h1>Beasiswa Unggulan 2026</h1><p>Pendaftaran '
    'dibuka sampai 30 November 2026 untuk mahasiswa aktif D3 hingga S2 di '
    'seluruh Indonesia.</p></main></body></html>')


def result(content: bytes, url: str = 'https://contoh.id/', *,
        content_type: str = 'text/html', status: int = 200,
        final_url: str | None = None) -> FetchResult:
    return FetchResult(requested_url=url, final_url=final_url or url,
        status=status, content_type=content_type, content=content,
        fetched_at=datetime.now(timezone.utc))


def test_needs_rendering_only_for_js_shells():
    assert needs_rendering(result(SHELL))
    assert not needs_rendering(result(RENDERED.encode()))
    assert not needs_rendering(result(b'%PDF-1.4', content_type='application/pdf'))


def test_with_rendering_is_a_noop_without_renderer_url():
    def fetcher(url):
        return result(SHELL, url)
    assert with_rendering(fetcher, '') is fetcher


def test_with_rendering_replaces_shell_with_rendered_dom():
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={'final_url': 'https://contoh.id/beasiswa',
            'status': 200, 'html': RENDERED})

    fetch = with_rendering(lambda url: result(SHELL, url), 'http://renderer:9000',
        client=httpx.Client(transport=httpx.MockTransport(handler)))
    rendered = fetch('https://contoh.id/')
    assert calls == [{'url': 'https://contoh.id/'}]
    assert rendered.rendered is True
    assert rendered.final_url == 'https://contoh.id/beasiswa'
    item = _fetch_evidence(fetch, 'https://contoh.id/', origin='submitted_url')
    assert item['rendered'] is True
    assert 'extract_error' not in item
    assert '30 November 2026' in item['text']


def test_with_rendering_skips_renderer_for_static_pages():
    def handler(request):
        raise AssertionError('renderer must not be called')

    fetch = with_rendering(lambda url: result(RENDERED.encode(), url),
        'http://renderer:9000',
        client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert fetch('https://contoh.id/').rendered is False


def test_with_rendering_falls_back_when_renderer_declines_or_is_down():
    for handler in (
        lambda request: httpx.Response(422, json={'error': 'forbidden_host'}),
        lambda request: (_ for _ in ()).throw(httpx.ConnectError('down')),
    ):
        fetch = with_rendering(lambda url: result(SHELL, url), 'http://renderer:9000',
            client=httpx.Client(transport=httpx.MockTransport(handler)))
        item = _fetch_evidence(fetch, 'https://contoh.id/', origin='submitted_url')
        assert item['extract_error'] == 'js_required'
        assert 'rendered' not in item


class FakeFrame:
    parent_frame = None


class FakeRequest:
    def __init__(self, url, *, resource_type='document', method='GET',
            navigation=True):
        self.url = url
        self.resource_type = resource_type
        self.method = method
        self._navigation = navigation
        self.frame = FakeFrame()

    def is_navigation_request(self):
        return self._navigation


class FakeRoute:
    def __init__(self):
        self.action = None

    def abort(self):
        self.action = ('abort',)

    def fulfill(self, *, status, body=b'', headers=None):
        self.action = ('fulfill', status, body, headers or {})


def budget(seconds: float = 30.0) -> _Budget:
    return _Budget(deadline=time.monotonic() + seconds, clock=time.monotonic)


def test_handler_serves_every_request_through_the_hardened_fetcher():
    seen = []

    def fetcher(url, **kwargs):
        seen.append((url, kwargs['max_bytes']))
        return result(b'console.log(1)', url, content_type='application/javascript')

    state = budget()
    route = FakeRoute()
    _handler(fetcher, state)(route, FakeRequest('https://cdn.contoh.id/app.js',
        resource_type='script', navigation=False))
    assert seen and seen[0][0] == 'https://cdn.contoh.id/app.js'
    assert route.action[0:3] == ('fulfill', 200, b'console.log(1)')
    assert route.action[3]['content-type'] == 'application/javascript'
    assert state.requests == 1


def test_handler_aborts_when_fetcher_rejects_private_hosts():
    def fetcher(url, **kwargs):
        raise FetchError('forbidden_host', 'resolves to a non-public address')

    route = FakeRoute()
    _handler(fetcher, budget())(route, FakeRequest('http://169.254.169.254/latest',
        resource_type='xhr', navigation=False))
    assert route.action == ('abort',)


def test_handler_skips_media_non_get_and_over_budget_requests():
    def fetcher(url, **kwargs):
        raise AssertionError('must not fetch')

    exhausted = budget()
    exhausted.requests = MAX_SUBREQUESTS
    cases = [
        (budget(), FakeRequest('https://contoh.id/a.png', resource_type='image')),
        (budget(), FakeRequest('https://contoh.id/api', resource_type='xhr', method='POST')),
        (exhausted, FakeRequest('https://contoh.id/b.js', resource_type='script')),
        (budget(0.1), FakeRequest('https://contoh.id/c.js', resource_type='script')),
    ]
    for state, request in cases:
        route = FakeRoute()
        _handler(fetcher, state)(route, request)
        assert route.action == ('abort',)


def test_handler_replays_redirects_for_navigation():
    def fetcher(url, **kwargs):
        return result(b'<html></html>', url, final_url='https://contoh.id/baru')

    route = FakeRoute()
    _handler(fetcher, budget())(route, FakeRequest('https://contoh.id/lama'))
    assert route.action[0:2] == ('fulfill', 302)
    assert route.action[3] == {'location': 'https://contoh.id/baru'}


def test_handler_passes_upstream_http_errors_through():
    def fetcher(url, **kwargs):
        raise FetchError('http_error', 'not found', status=404)

    route = FakeRoute()
    _handler(fetcher, budget())(route, FakeRequest('https://contoh.id/hilang'))
    assert route.action[0:2] == ('fulfill', 404)

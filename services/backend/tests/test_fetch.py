import io
import socket

import httpx
import pytest
from pypdf import PdfWriter

from app.services.extract import MAX_EXTRACT_CHARS, page_text, to_text
from app.services.fetch import FetchError, FetchResult, fetch

PUBLIC_IP = '93.184.216.34'


def resolver_for(*ips, calls=None):
    def resolve(host, port):
        if calls is not None:
            calls.append((host, port))
        return list(ips)
    return resolve


def never_transport():
    def handler(request):
        raise AssertionError('transport must not be reached')
    return httpx.MockTransport(handler)


def test_fetch_returns_result_and_pins_connection():
    seen = []
    calls = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200,
            headers={'content-type': 'text/html; charset=utf-8'},
            content=b'<html>ok</html>')

    result = fetch('https://example.org/page?x=1',
        resolver=resolver_for(PUBLIC_IP, calls=calls),
        transport=httpx.MockTransport(handler))
    assert isinstance(result, FetchResult)
    assert result.requested_url == 'https://example.org/page?x=1'
    assert result.final_url == 'https://example.org/page?x=1'
    assert result.status == 200
    assert result.content_type == 'text/html'
    assert result.content == b'<html>ok</html>'
    assert result.fetched_at.tzinfo is not None
    assert calls == [('example.org', 443)]
    request = seen[0]
    assert request.url.host == PUBLIC_IP
    assert request.headers['host'] == 'example.org'
    assert request.extensions['sni_hostname'] == 'example.org'
    assert 'cookie' not in request.headers
    assert 'authorization' not in request.headers


def test_fetch_pins_http_with_host_header_and_no_sni():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, content=b'ok')

    fetch('http://example.org/', resolver=resolver_for(PUBLIC_IP),
        transport=httpx.MockTransport(handler))
    request = seen[0]
    assert request.url.host == PUBLIC_IP
    assert request.headers['host'] == 'example.org'
    assert 'sni_hostname' not in request.extensions


@pytest.mark.parametrize('ip', [
    '127.0.0.1', '10.0.0.5', '169.254.169.254', '172.16.0.1', '192.168.1.1',
    '::1', '::ffff:127.0.0.1', '100.64.0.1', '203.0.113.1',
    '64:ff9b::7f00:1', '64:ff9b::a9fe:a9fe', '64:ff9b::c0a8:101'])
def test_fetch_rejects_non_public_resolved_ips(ip):
    with pytest.raises(FetchError) as exc:
        fetch('http://example.org/', resolver=resolver_for(ip),
            transport=never_transport())
    assert exc.value.kind == 'forbidden_host'


def test_fetch_rejects_when_any_resolved_ip_is_private():
    with pytest.raises(FetchError) as exc:
        fetch('http://example.org/',
            resolver=resolver_for(PUBLIC_IP, '127.0.0.1'),
            transport=never_transport())
    assert exc.value.kind == 'forbidden_host'


def test_fetch_allows_nat64_wrapped_public_ip():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, content=b'ok')

    fetch('http://example.org/', resolver=resolver_for('64:ff9b::808:808'),
        transport=httpx.MockTransport(handler))
    assert seen[0].url.host == '64:ff9b::808:808'


def test_fetch_allows_public_ip_literal_without_dns():
    seen = []

    def resolver(host, port):
        raise AssertionError('dns must be skipped for ip literals')

    def handler(request):
        seen.append(request)
        return httpx.Response(200, content=b'ok')

    fetch('http://93.184.216.34/x', resolver=resolver,
        transport=httpx.MockTransport(handler))
    request = seen[0]
    assert request.url.host == PUBLIC_IP
    assert request.headers['host'] == PUBLIC_IP


@pytest.mark.parametrize('url', [
    'http://127.0.0.1/x', 'http://0x7f.0.0.1/x', 'http://2130706433/x',
    'http://[::1]/x'])
def test_fetch_rejects_private_ip_literals(url):
    with pytest.raises(FetchError) as exc:
        fetch(url, transport=never_transport())
    assert exc.value.kind in ('forbidden_host', 'invalid_url')


@pytest.mark.parametrize('url', [
    'ftp://x', 'http://u:p@h/x', 'http://h:8080/', 'http://h:notaport/'])
def test_fetch_rejects_invalid_urls(url):
    with pytest.raises(FetchError) as exc:
        fetch(url, transport=never_transport())
    assert exc.value.kind == 'invalid_url'


def test_fetch_revalidates_redirect_targets():
    resolvers = {'example.org': [PUBLIC_IP], 'evil.internal': ['10.1.2.3']}

    def resolver(host, port):
        return resolvers[host]

    def handler(request):
        if request.url.host == PUBLIC_IP:
            return httpx.Response(302,
                headers={'location': 'http://evil.internal/'})
        raise AssertionError('redirect target must not be fetched')

    with pytest.raises(FetchError) as exc:
        fetch('http://example.org/', resolver=resolver,
            transport=httpx.MockTransport(handler))
    assert exc.value.kind == 'forbidden_host'


def test_fetch_follows_redirect_to_public_host():
    seen = []
    resolvers = {'example.org': [PUBLIC_IP], 'cdn.example.org': ['8.8.8.8']}

    def resolver(host, port):
        return resolvers[host]

    def handler(request):
        seen.append(request)
        if request.url.host == PUBLIC_IP:
            return httpx.Response(302,
                headers={'location': 'http://cdn.example.org/final'})
        return httpx.Response(200,
            headers={'content-type': 'text/plain'}, content=b'done')

    result = fetch('http://example.org/', resolver=resolver,
        transport=httpx.MockTransport(handler))
    assert result.final_url == 'http://cdn.example.org/final'
    assert result.content == b'done'
    assert seen[1].url.host == '8.8.8.8'
    assert seen[1].headers['host'] == 'cdn.example.org'


def test_fetch_aborts_body_read_at_wall_clock_deadline():
    # A slow-drip server must not hold the worker past the per-page budget
    # even when each individual socket read returns within the httpx timeout.
    calls = [0]
    def clock():
        calls[0] += 1
        return 0.0 if calls[0] <= 2 else 100.0

    def handler(request):
        return httpx.Response(200, content=iter([b'a' * 8, b'b' * 8]))

    with pytest.raises(FetchError) as exc:
        fetch('http://example.org/', resolver=resolver_for(PUBLIC_IP),
            transport=httpx.MockTransport(handler), clock=clock)
    assert exc.value.kind == 'timeout'


def test_fetch_limits_redirects():
    counter = {'n': 0}

    def handler(request):
        counter['n'] += 1
        return httpx.Response(302,
            headers={'location': f'http://example.org/{counter["n"]}'})

    with pytest.raises(FetchError) as exc:
        fetch('http://example.org/', resolver=resolver_for(PUBLIC_IP),
            transport=httpx.MockTransport(handler), max_redirects=3)
    assert exc.value.kind == 'too_many_redirects'
    assert counter['n'] == 4


def test_fetch_detects_redirect_loops():
    def handler(request):
        return httpx.Response(302,
            headers={'location': 'http://example.org/'})

    with pytest.raises(FetchError) as exc:
        fetch('http://example.org/', resolver=resolver_for(PUBLIC_IP),
            transport=httpx.MockTransport(handler))
    assert exc.value.kind == 'too_many_redirects'


def test_fetch_rejects_redirect_to_file_scheme():
    def handler(request):
        return httpx.Response(302,
            headers={'location': 'file:///etc/passwd'})

    with pytest.raises(FetchError) as exc:
        fetch('http://example.org/', resolver=resolver_for(PUBLIC_IP),
            transport=httpx.MockTransport(handler))
    assert exc.value.kind in ('invalid_url', 'bad_redirect')


def test_fetch_redirect_without_location_is_http_error():
    def handler(request):
        return httpx.Response(301)

    with pytest.raises(FetchError) as exc:
        fetch('http://example.org/', resolver=resolver_for(PUBLIC_IP),
            transport=httpx.MockTransport(handler))
    assert exc.value.kind == 'http_error'
    assert exc.value.status == 301


def test_fetch_maps_404_to_http_error():
    def handler(request):
        return httpx.Response(404, content=b'nope')

    with pytest.raises(FetchError) as exc:
        fetch('http://example.org/', resolver=resolver_for(PUBLIC_IP),
            transport=httpx.MockTransport(handler))
    assert exc.value.kind == 'http_error'
    assert exc.value.status == 404


def test_fetch_aborts_when_body_exceeds_max_bytes():
    def handler(request):
        return httpx.Response(200, content=b'x' * 1024)

    with pytest.raises(FetchError) as exc:
        fetch('http://example.org/', resolver=resolver_for(PUBLIC_IP),
            transport=httpx.MockTransport(handler), max_bytes=10)
    assert exc.value.kind == 'too_large'


def test_fetch_maps_connect_timeout():
    def handler(request):
        raise httpx.ConnectTimeout('boom', request=request)

    with pytest.raises(FetchError) as exc:
        fetch('http://example.org/', resolver=resolver_for(PUBLIC_IP),
            transport=httpx.MockTransport(handler))
    assert exc.value.kind in ('timeout', 'connect_failed')


def test_fetch_maps_connect_error():
    def handler(request):
        raise httpx.ConnectError('refused', request=request)

    with pytest.raises(FetchError) as exc:
        fetch('http://example.org/', resolver=resolver_for(PUBLIC_IP),
            transport=httpx.MockTransport(handler))
    assert exc.value.kind == 'connect_failed'


def test_fetch_maps_dns_failure():
    def resolver(host, port):
        raise socket.gaierror('no such host')

    with pytest.raises(FetchError) as exc:
        fetch('http://example.org/', resolver=resolver,
            transport=never_transport())
    assert exc.value.kind == 'dns_blocked'


def test_fetch_maps_empty_resolution_to_dns_blocked():
    with pytest.raises(FetchError) as exc:
        fetch('http://example.org/', resolver=resolver_for(),
            transport=never_transport())
    assert exc.value.kind == 'dns_blocked'


def test_fetch_never_sends_cookies_across_redirects():
    seen = []
    resolvers = {'example.org': [PUBLIC_IP], 'cdn.example.org': ['8.8.8.8']}

    def resolver(host, port):
        return resolvers[host]

    def handler(request):
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(302, headers={
                'location': 'http://cdn.example.org/',
                'set-cookie': 'session=secret'})
        return httpx.Response(200, content=b'ok')

    fetch('http://example.org/', resolver=resolver,
        transport=httpx.MockTransport(handler))
    assert len(seen) == 2
    assert 'cookie' not in seen[1].headers


def test_to_text_extracts_main_html_content():
    html = b'''<html><head><title>Test</title>
        <script>var tracker = 1;</script><style>.x{color:red}</style>
        </head><body>
        <nav><a href='/'>Beranda</a> <a href='/login'>Masuk</a></nav>
        <article><h1>Beasiswa Unggulan 2026</h1>
        <p>Pemerintah membuka pendaftaran beasiswa unggulan bagi mahasiswa
        baru tahun ajaran 2026/2027. Program ini mencakup biaya kuliah
        penuh serta tunjangan hidup bulanan selama masa studi.</p>
        <p>Pendaftaran dibuka mulai 1 Februari hingga 31 Maret 2026
        melalui laman resmi. Peserta wajib melampirkan transkrip nilai.</p>
        </article><footer>Hubungi kami</footer></body></html>'''
    text = to_text(html, 'text/html')
    assert 'Beasiswa Unggulan 2026' in text
    assert 'Pemerintah membuka pendaftaran' in text
    assert 'tracker' not in text
    assert 'Beranda' not in text


def test_to_text_sniffs_html_without_content_type():
    text = to_text(b'<html><body><p>halo dunia</p></body></html>', None)
    assert 'halo dunia' in text


def test_to_text_pdf_bytes_return_string():
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    assert isinstance(to_text(buf.getvalue(), 'application/pdf'), str)
    assert isinstance(to_text(buf.getvalue(), None), str)


def test_to_text_returns_empty_for_broken_pdf():
    assert to_text(b'%PDF-1.7 garbage', 'application/pdf') == ''


def test_to_text_returns_empty_for_images():
    assert to_text(b'\x89PNG\r\n\x1a\n....', 'image/png') == ''


def test_to_text_decodes_text_and_json():
    assert to_text('halo \u00e9'.encode(), 'text/plain; charset=utf-8') == 'halo \u00e9'
    assert to_text(b'{"a": 1}', 'application/json') == '{"a": 1}'
    assert to_text(b'{"a": 1}', 'application/hal+json') == '{"a": 1}'


def test_to_text_caps_output():
    text = to_text(b'a' * (MAX_EXTRACT_CHARS + 100), 'text/plain')
    assert len(text) == MAX_EXTRACT_CHARS


def test_to_text_fallback_strips_script_and_style():
    html = (b'<html><body><script>evil()</script><style>x{}</style>'
        b'<p>isi utama</p></body></html>')
    text = to_text(html, 'text/html')
    assert 'isi utama' in text
    assert 'evil()' not in text


SPA_SHELL = (b'<!doctype html><html><head><title>App</title></head>'
    b'<body><noscript>You need to enable JavaScript to run this app.'
    b'</noscript><div id="root"></div>'
    b'<script src="/static/js/main.js"></script></body></html>')


def test_to_text_never_returns_noscript_fallback():
    text = to_text(SPA_SHELL, 'text/html')
    assert 'JavaScript' not in text


def test_page_text_flags_js_shell():
    # A client-rendered mount page is not evidence — flag it so the LLM is
    # never fed the noscript fallback string as page content.
    text, error = page_text(SPA_SHELL, 'text/html')
    assert text == ''
    assert error == 'js_required'


def test_page_text_reads_server_rendered_html_with_noscript():
    html = (b'<html><body><noscript>Aktifkan JavaScript.</noscript>'
        b'<article><h1>Beasiswa Unggulan 2026</h1><p>Pendaftaran dibuka'
        b' hingga 31 Maret melalui portal resmi kemdikbud.</p>'
        b'</article></body></html>')
    text, error = page_text(html, 'text/html')
    assert error is None
    assert 'Beasiswa Unggulan' in text
    assert 'Aktifkan JavaScript' not in text


def test_page_text_empty_html_without_shell_markers():
    text, error = page_text(b'<html><body></body></html>', 'text/html')
    assert text == ''
    assert error == 'empty_content'


def test_page_text_empty_for_binary_content():
    text, error = page_text(b'\x89PNG\r\n\x1a\n....', 'image/png')
    assert text == ''
    assert error == 'empty_content'

"""Best-effort text extraction for fetched content; never raises — the
worst case for malformed input is an empty string."""

import io
from html import escape
from html.parser import HTMLParser

import trafilatura
from pypdf import PdfReader

MAX_EXTRACT_CHARS = 50_000

_HTML_TYPES = {'text/html', 'application/xhtml+xml'}
_TEXT_SUFFIXES = ('+json', '+xml')
_SKIP_TAGS = frozenset({'head', 'script', 'style', 'noscript', 'template',
    'svg', 'iframe'})
_BLOCK_TAGS = frozenset({'p', 'div', 'br', 'li', 'ul', 'ol', 'tr', 'table',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'section', 'article', 'header',
    'footer', 'blockquote', 'pre'})
_HTML_MARKERS = (b'<html', b'<!doctype html', b'<head', b'<body', b'<title',
    b'<article', b'<p>', b'<div')
_JS_SHELL_MARKERS = (b'<noscript', b'id="root"', b"id='root'", b'id="app"',
    b"id='app'", b'id="__next"', b'id="__nuxt"', b'data-reactroot',
    b'ng-app', b'ng-version')


def to_text(content: bytes, content_type: str | None) -> str:
    media = (content_type or '').split(';', 1)[0].strip().lower()
    try:
        if media == 'application/pdf' or content.startswith(b'%PDF-'):
            text = _pdf_text(content)
        elif media in _HTML_TYPES or (not media
                and _looks_like_html(content)):
            text = _html_text(content)
        elif (media.startswith('text/') or media == 'application/json'
                or media.endswith(_TEXT_SUFFIXES)):
            text = content[:MAX_EXTRACT_CHARS * 4].decode(
                'utf-8', errors='replace')
        else:
            return ''
    except Exception:
        return ''
    return text[:MAX_EXTRACT_CHARS]


def page_text(content: bytes, content_type: str | None) -> tuple[str, str | None]:
    """Extracted text plus a reason kind when nothing readable came back.

    Kinds: 'js_required' (a client-rendered shell such as a React/Vue mount
    page), 'empty_content' (fetched fine but no usable text). Noscript
    fallback text never counts as content — a JS-only page must surface as
    unreadable rather than feed its 'enable JavaScript' hint to the LLM.
    """
    text = to_text(content, content_type)
    if text.strip():
        return text, None
    media = (content_type or '').split(';', 1)[0].strip().lower()
    if media in _HTML_TYPES or (not media and _looks_like_html(content)):
        head = content[:131_072].lower()
        if any(marker in head for marker in _JS_SHELL_MARKERS):
            return '', 'js_required'
    return '', 'empty_content'


def _looks_like_html(content: bytes) -> bool:
    head = content[:1024].lower()
    return any(marker in head for marker in _HTML_MARKERS)


def _pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return '\n'.join(page.extract_text() or '' for page in reader.pages)


def _html_text(content: bytes) -> str:
    html = content.decode('utf-8', errors='replace')
    # trafilatura parses noscript/template/svg fallback text as content —
    # strip those subtrees first so a JS-only page extracts to empty.
    lowered = html.lower()
    if any(hint in lowered for hint in _SANITIZE_HINTS):
        html = _sanitize(html)
    text = trafilatura.extract(html, include_links=False,
        include_images=False, include_tables=True)
    return text if text is not None else _strip_tags(html)


_SANITIZE_HINTS = ('<noscript', '<template', '<svg', '<iframe')
_VOID_TAGS = frozenset({'area', 'base', 'br', 'col', 'embed', 'hr', 'img',
    'input', 'link', 'meta', 'source', 'track', 'wbr'})


class _Sanitizer(HTMLParser):
    """Re-emit the document without skip-tag subtrees (noscript, template,
    svg, iframe, script, style). Fallback and script markup is never page
    content — leaving it in lets trafilatura return 'enable JavaScript'
    strings as if they were the article."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def _start(self, tag, attrs, closing=''):
        if tag in _SKIP_TAGS:
            self._skip += 1
            return
        if self._skip:
            return
        rendered = ''.join(
            f' {name}' if value is None else
            f' {name}="{escape(value, quote=True)}"'
            for name, value in attrs)
        self.parts.append(f'<{tag}{rendered}{closing}>')

    def handle_starttag(self, tag, attrs):
        self._start(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            return
        self._start(tag, attrs, closing=' /')

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif not self._skip and tag not in _VOID_TAGS:
            self.parts.append(f'</{tag}>')

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(escape(data, quote=False))

    def handle_entityref(self, name):
        if not self._skip:
            self.parts.append(f'&{name};')

    def handle_charref(self, name):
        if not self._skip:
            self.parts.append(f'&#{name};')


def _sanitize(html: str) -> str:
    sanitizer = _Sanitizer()
    try:
        sanitizer.feed(html)
        sanitizer.close()
    except Exception:
        return html
    return ''.join(sanitizer.parts)


class _TextExtractor(HTMLParser):
    """Stdlib fallback: collect character data, skip script/style subtrees,
    and treat block-level tags as line breaks."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip += 1
        elif not self._skip and tag in _BLOCK_TAGS:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif not self._skip and tag in _BLOCK_TAGS:
            self.parts.append('\n')

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _strip_tags(html: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        pass
    lines = (' '.join(line.split())
        for line in ''.join(parser.parts).splitlines())
    return '\n'.join(line for line in lines if line)

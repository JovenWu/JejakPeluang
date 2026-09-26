"""Best-effort text extraction for fetched content; never raises — the
worst case for malformed input is an empty string."""

import io
from html.parser import HTMLParser

import trafilatura
from pypdf import PdfReader

MAX_EXTRACT_CHARS = 50_000

_HTML_TYPES = {'text/html', 'application/xhtml+xml'}
_TEXT_SUFFIXES = ('+json', '+xml')
_SKIP_TAGS = frozenset({'script', 'style'})
_BLOCK_TAGS = frozenset({'p', 'div', 'br', 'li', 'ul', 'ol', 'tr', 'table',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'section', 'article', 'header',
    'footer', 'blockquote', 'pre'})
_HTML_MARKERS = (b'<html', b'<!doctype html', b'<head', b'<body', b'<title',
    b'<article', b'<p>', b'<div')


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


def _looks_like_html(content: bytes) -> bool:
    head = content[:1024].lower()
    return any(marker in head for marker in _HTML_MARKERS)


def _pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return '\n'.join(page.extract_text() or '' for page in reader.pages)


def _html_text(content: bytes) -> str:
    html = content.decode('utf-8', errors='replace')
    text = trafilatura.extract(html, include_links=False,
        include_images=False, include_tables=True)
    return text if text is not None else _strip_tags(html)


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

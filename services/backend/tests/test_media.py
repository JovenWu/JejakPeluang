import io

import pytesseract
import qrcode
from PIL import Image

from app.services.media import image_urls_from_html, inspect_image, pdf_image_bytes


def qr_png(value: str) -> bytes:
    image = qrcode.make(value)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def test_inspect_image_decodes_http_qr_even_when_ocr_is_unavailable():
    text, urls, error = inspect_image(qr_png('https://kemdikbud.go.id/daftar'))

    assert text == ''
    assert urls == ['https://kemdikbud.go.id/daftar']
    assert error in (None, 'ocr_unavailable')


def test_inspect_image_ignores_non_web_qr_payloads():
    _, urls, _ = inspect_image(qr_png('mailto:daftar@example.org'))

    assert urls == []


def test_inspect_image_uses_indonesian_ocr(monkeypatch):
    seen = {}

    def read_text(image, *, lang, timeout):
        seen['lang'] = lang
        seen['timeout'] = timeout
        return 'Program beasiswa untuk mahasiswa.'

    monkeypatch.setattr(pytesseract, 'image_to_string', read_text)
    image = Image.new('RGB', (40, 40), 'white')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')

    text, urls, error = inspect_image(buffer.getvalue())

    assert text == 'Program beasiswa untuk mahasiswa.'
    assert urls == []
    assert error is None
    assert seen == {'lang': 'ind+eng', 'timeout': 8}


def test_image_urls_from_html_reads_social_preview_and_responsive_images():
    html = (b'<html><head><meta property="og:image" content="/poster.png">'
        b'</head><body><img src="/first.jpg" srcset="/small.jpg 1x, '
        b'/large.jpg 2x"><img src="   "></body></html>')

    assert image_urls_from_html(html, 'https://instagram.com/p/123/') == [
        'https://instagram.com/poster.png',
        'https://instagram.com/first.jpg',
        'https://instagram.com/small.jpg',
    ]


def test_pdf_image_bytes_returns_empty_for_text_only_pdf():
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)

    assert pdf_image_bytes(buffer.getvalue()) == []

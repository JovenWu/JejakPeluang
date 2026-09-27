from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import urljoin, urlsplit

from pypdf import PdfReader

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_IMAGE_URLS = 3
MAX_PDF_IMAGES = 6
MAX_OCR_CHARS = 8_000


def _web_url(value: str) -> str | None:
    value = value.strip()
    if not value or len(value) > 2048:
        return None
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        return None
    if (parts.scheme not in ('http', 'https') or not parts.hostname
            or parts.username is not None or parts.password is not None
            or port not in (None, 80, 443)):
        return None
    return value


class _ImageURLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.values: list[str] = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'meta' and attributes.get('property', '').lower() in (
                'og:image', 'og:image:url', 'twitter:image'):
            value = attributes.get('content')
            if value:
                self.values.append(value)
        if tag in ('img', 'source'):
            for name in ('src', 'data-src', 'srcset'):
                value = attributes.get(name)
                if not value:
                    continue
                candidate = value
                if name == 'srcset':
                    sources = [source.strip() for source in value.split(',')
                        if source.strip()]
                    candidate = sources[0].split()[0] if sources else ''
                if candidate:
                    self.values.append(candidate)


def image_urls_from_html(content: bytes, base_url: str) -> list[str]:
    parser = _ImageURLParser()
    try:
        parser.feed(content.decode('utf-8', errors='replace'))
    except Exception:
        return []
    urls: list[str] = []
    for value in parser.values:
        url = _web_url(urljoin(base_url, value))
        if url and url not in urls:
            urls.append(url)
        if len(urls) >= MAX_IMAGE_URLS:
            break
    return urls


def pdf_image_bytes(content: bytes) -> list[bytes]:
    try:
        pages = PdfReader(BytesIO(content)).pages
    except Exception:
        return []
    images: list[bytes] = []
    for page in pages:
        try:
            for image in page.images:
                data = image.data
                if data and len(data) <= MAX_IMAGE_BYTES:
                    images.append(data)
                if len(images) >= MAX_PDF_IMAGES:
                    return images
        except Exception:
            continue
    return images


def inspect_image(content: bytes) -> tuple[str, list[str], str | None]:
    if not content or len(content) > MAX_IMAGE_BYTES:
        return '', [], 'media_too_large' if content else 'unreadable_image'
    try:
        from PIL import Image
        import pytesseract
        from pyrxing import read_barcodes

        with Image.open(BytesIO(content)) as source:
            if source.width * source.height > MAX_IMAGE_PIXELS:
                return '', [], 'image_too_large'
            source.load()
            image = source.convert('RGB')
    except Exception:
        return '', [], 'unreadable_image'

    urls: list[str] = []
    try:
        for barcode in read_barcodes(image, formats=['QRCode']):
            url = _web_url(barcode.text)
            if url and url not in urls:
                urls.append(url)
            if len(urls) >= 4:
                break
    except Exception:
        pass

    try:
        text = pytesseract.image_to_string(image, lang='ind+eng', timeout=8)
        return text[:MAX_OCR_CHARS].strip(), urls, None
    except pytesseract.TesseractNotFoundError:
        return '', urls, 'ocr_unavailable'
    except RuntimeError:
        return '', urls, 'ocr_timeout'
    except Exception:
        return '', urls, 'ocr_failed'

"""Worker-side hook that sends JavaScript-only pages to the renderer."""

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from os import environ

import httpx

from app.services.extract import page_text
from app.services.fetch import FetchResult

logger = logging.getLogger(__name__)
RENDER_REQUEST_TIMEOUT_SECONDS = 40.0

Fetcher = Callable[[str], FetchResult]


def needs_rendering(result: FetchResult) -> bool:
    return page_text(result.content, result.content_type)[1] == 'js_required'


def with_rendering(fetcher: Fetcher, renderer_url: str | None = None, *,
        client: httpx.Client | None = None) -> Fetcher:
    """Wrap ``fetcher`` so client-rendered shells come back rendered.

    Rendering is best-effort: if the renderer is unset, down, or rejects
    the page, the original static fetch is returned and extraction reports
    ``js_required`` exactly as before.
    """
    base = renderer_url if renderer_url is not None else environ.get('RENDERER_URL')
    if not base:
        return fetcher
    http = client or httpx.Client(timeout=RENDER_REQUEST_TIMEOUT_SECONDS)
    endpoint = f"{base.rstrip('/')}/render"

    def fetch_and_render(url: str) -> FetchResult:
        result = fetcher(url)
        if not needs_rendering(result):
            return result
        try:
            response = http.post(endpoint, json={'url': result.final_url})
        except httpx.HTTPError as exc:
            logger.warning('renderer unreachable for %s: %s', url, exc)
            return result
        if response.status_code != 200:
            logger.info('renderer declined %s: %s %s', url,
                response.status_code, response.text[:200])
            return result
        body = response.json()
        return FetchResult(requested_url=url, final_url=body['final_url'],
            status=body['status'], content_type='text/html',
            content=body['html'].encode('utf-8'),
            fetched_at=datetime.now(timezone.utc), rendered=True)

    return fetch_and_render

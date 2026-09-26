"""Tavily discovery adapter — candidate-source search only.

Search is for discovery: a hit is a lead to fetch and verify, never evidence
(spec: search ranking/snippets do not establish trust). Queries are minimized
to the extracted title + issuer — never the whole submission.
"""
import logging
from os import environ
from typing import Any

import httpx

from app.services.providers import ProviderError, post_json

logger = logging.getLogger(__name__)

BASE_URL = 'https://api.tavily.com'
MAX_RESULTS = 5
MAX_QUERY_CHARS = 300


class TavilySearcher:
    """POSTs /search and returns raw candidate dicts; injectable client."""

    def __init__(self, *, api_key: str | None = None,
        base_url: str | None = None, client: httpx.Client | None = None,
        sleeper=None):
        self.api_key = api_key if api_key is not None else environ.get(
            'TAVILY_API_KEY', '')
        self.base_url = (base_url or environ.get('TAVILY_BASE_URL')
            or BASE_URL).rstrip('/')
        self.client = client
        self.sleeper = sleeper

    def search(self, title: str | None, issuer: str | None, *,
            include_domains: list[str] | None = None) -> list[dict[str, Any]]:
        """Minimized query: title + issuer only. Returns [{'url','title'}]."""
        if not self.api_key:
            raise ProviderError('config', 'TAVILY_API_KEY is not set')
        terms = ' '.join(part for part in (title, issuer) if part).strip()
        if not terms:
            return []
        payload: dict[str, Any] = {
            'query': terms[:MAX_QUERY_CHARS],
            'max_results': MAX_RESULTS,
            'search_depth': 'basic',
            'include_answer': False,
            'include_raw_content': False,
        }
        if include_domains:
            payload['include_domains'] = include_domains
        body = post_json(f'{self.base_url}/search',
            headers={'Authorization': f'Bearer {self.api_key}'},
            payload=payload, client=self.client, sleeper=self.sleeper,
            label='tavily')
        results = body.get('results') or []
        candidates = []
        for item in results:
            if not isinstance(item, dict):
                continue
            url = item.get('url')
            if isinstance(url, str) and url:
                candidates.append({'url': url,
                    'title': item.get('title') or ''})
        return candidates

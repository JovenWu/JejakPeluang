"""Shared plumbing for outbound provider calls (OpenRouter, Tavily, TypeSafe).

Every provider call goes through post_json, which applies the spec's retry
policy: at most 3 attempts, exponential backoff with jitter, honouring
Retry-After; 4xx other than 429 are permanent and fail immediately.
"""
import logging
import random
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
DEFAULT_TIMEOUT_SECONDS = 15.0
# A Retry-After beyond this cannot be honoured inside a screening run's
# 300 s deadline — fail fast instead of wedging the worker on a sleep.
MAX_RETRY_DELAY_SECONDS = 30.0
_RETRY_STATUSES = {408, 409, 425, 429, 500, 502, 503, 504}


class ProviderError(Exception):
    """Retryable-ness is decided inside post_json; this is the terminal
    failure surfaced to the pipeline (kind: 'timeout', 'http', 'connect',
    'bad_response')."""

    def __init__(self, kind: str, detail: str, *, status: int | None = None):
        super().__init__(detail)
        self.kind = kind
        self.detail = detail
        self.status = status


class ProviderUnavailable(ProviderError):
    """Retries exhausted (or hard failure): spec maps this to
    'provider_unavailable', which routes to moderator review — never a
    fraud verdict."""

    def __init__(self, detail: str, *, status: int | None = None):
        super().__init__('provider_unavailable', detail, status=status)


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get('retry-after')
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def post_json(url: str, *, headers: dict[str, str], payload: dict[str, Any],
        timeout: float = DEFAULT_TIMEOUT_SECONDS, max_attempts: int = MAX_ATTEMPTS,
        client: httpx.Client | None = None,
        sleeper=None, label: str = 'provider') -> dict[str, Any]:
    """POST a JSON body and return the decoded JSON object.

    ``client``/``sleeper`` are injectable for tests. Retries on timeouts,
    connection errors, 429 and 5xx (honouring Retry-After); any other 4xx
    fails permanently at once. Returns the parsed object or raises
    ProviderUnavailable/ProviderError.
    """
    own_client = client is None
    client = client or httpx.Client(timeout=timeout)
    sleeper = sleeper or time.sleep
    last_error: ProviderError | None = None
    try:
        for attempt in range(1, max_attempts + 1):
            try:
                response = client.post(url, json=payload, headers=headers)
            except httpx.TimeoutException:
                last_error = ProviderError('timeout', f'{label} timed out')
            except httpx.TransportError as exc:
                last_error = ProviderError('connect',
                    f'{label} connection failed: {exc.__class__.__name__}')
            else:
                if response.status_code in _RETRY_STATUSES:
                    last_error = ProviderError('http',
                        f'{label} returned {response.status_code}',
                        status=response.status_code)
                    delay = _retry_after_seconds(response)
                    if delay is not None and delay > MAX_RETRY_DELAY_SECONDS:
                        raise ProviderUnavailable(
                            f'{label} asked to retry in {delay:.0f}s')
                    if delay is None:
                        delay = 0.5 * (2 ** (attempt - 1)) + random.uniform(0, 0.25)
                    if attempt < max_attempts:
                        sleeper(delay)
                    continue
                if response.status_code >= 400:
                    raise ProviderError('http',
                        f'{label} returned {response.status_code}',
                        status=response.status_code)
                try:
                    body = response.json()
                except ValueError:
                    raise ProviderError('bad_response',
                        f'{label} returned non-JSON body')
                if not isinstance(body, dict):
                    raise ProviderError('bad_response',
                        f'{label} returned non-object JSON')
                return body
            if attempt < max_attempts:
                delay = (0.5 * (2 ** (attempt - 1))
                    + random.uniform(0, 0.25))
                sleeper(delay)
        raise ProviderUnavailable(last_error.detail if last_error
            else f'{label} unavailable')
    finally:
        if own_client:
            client.close()

"""OpenRouter adapter for the screening pipeline (extraction + comparison).

Two narrow structured-output calls, both OpenAI-compatible chat completions
with a JSON-schema response_format. The model extracts fields and compares
them against fetched evidence — it never emits legitimacy/scam verdicts.
"""
import json
import logging
from os import environ
from typing import Any

import httpx

from app.services.providers import ProviderError, post_json

logger = logging.getLogger(__name__)

BASE_URL = 'https://openrouter.ai/api/v1'
DEFAULT_MODEL = 'openai/gpt-6-luna'

CATEGORIES = ['scholarship', 'internship', 'competition']

EXTRACTION_SCHEMA: dict[str, Any] = {
    'type': 'object',
    'additionalProperties': False,
    'properties': {
        'title': {'type': ['string', 'null']},
        'issuer': {'type': ['string', 'null']},
        'deadline': {'type': ['string', 'null'],
            'description': 'ISO 8601 date YYYY-MM-DD if stated, else null'},
        'category': {'type': ['string', 'null'], 'enum': CATEGORIES + [None]},
        'region': {'type': ['string', 'null']},
        'eligibility': {'type': ['string', 'null']},
        'fees': {'type': ['string', 'null'],
            'description': 'Any fees or payments the notice asks for'},
        'requested_data': {'type': 'array', 'items': {'type': 'string'},
            'description': 'Personal data/documents the notice asks for'},
        'source_hint': {'type': ['string', 'null'],
            'description': 'URL or site named as the announcement source'},
    },
    'required': ['title', 'issuer', 'deadline', 'category', 'region',
        'eligibility', 'fees', 'requested_data', 'source_hint'],
}

_VERDICT = {'type': 'object', 'additionalProperties': False, 'properties': {
    'verdict': {'type': 'string',
        'enum': ['supported', 'conflicting', 'not_found', 'unreadable']},
    'quote': {'type': ['string', 'null'],
        'description': 'Short verbatim evidence excerpt, or null'},
}, 'required': ['verdict', 'quote']}

COMPARISON_SCHEMA: dict[str, Any] = {
    'type': 'object',
    'additionalProperties': False,
    'properties': {
        'field_verdicts': {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'title': _VERDICT,
                'issuer': _VERDICT,
                'deadline': _VERDICT,
                'category': _VERDICT,
                'region': _VERDICT,
                'eligibility': _VERDICT,
            },
            'required': ['title', 'issuer', 'deadline', 'category', 'region',
                'eligibility'],
        },
        'notes': {'type': ['string', 'null'],
            'description': 'At most two sentences of neutral notes for the '
                'moderator, or null'},
    },
    'required': ['field_verdicts', 'notes'],
}

_EXTRACT_SYSTEM = (
    'You extract structured fields from an opportunity announcement '
    '(Indonesian or English): scholarships, internships, competitions. '
    'Answer with JSON matching the schema exactly. Use null for fields the '
    'text does not state. Never invent values.')

_COMPARE_SYSTEM = (
    'You compare submitted opportunity details against fetched source page '
    'text. For each field decide whether the evidence supports it, conflicts '
    'with it, does not mention it (not_found), or is unreadable. Judge only '
    'the listed fields from the provided text; never assess legitimacy, '
    'trust, or fraud. Keep quotes short and verbatim.')


class OpenRouterClient:
    """Thin OpenAI-compatible client; injectable/session-free for tests."""

    def __init__(self, *, api_key: str | None = None,
        model: str | None = None, base_url: str | None = None,
        client: httpx.Client | None = None,
        sleeper=None):
        self.api_key = api_key if api_key is not None else environ.get(
            'OPENROUTER_API_KEY', '')
        self.model = model or environ.get('OPENROUTER_MODEL', DEFAULT_MODEL)
        self.base_url = (base_url or environ.get('OPENROUTER_BASE_URL')
            or BASE_URL).rstrip('/')
        self.client = client
        self.sleeper = sleeper

    def _chat_schema(self, system: str, user: dict[str, Any],
            name: str, schema: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise ProviderError('config', 'OPENROUTER_API_KEY is not set')
        payload = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': json.dumps(user,
                    ensure_ascii=False)},
            ],
            'response_format': {'type': 'json_schema', 'json_schema': {
                'name': name, 'strict': True, 'schema': schema}},
            'temperature': 0,
        }
        body = post_json(f'{self.base_url}/chat/completions',
            headers={'Authorization': f'Bearer {self.api_key}'},
            payload=payload, client=self.client, sleeper=self.sleeper,
            label='openrouter')
        try:
            content = body['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError):
            raise ProviderError('bad_response',
                'openrouter response missing choices[0].message.content')
        if not isinstance(content, str) or not content.strip():
            raise ProviderError('bad_response',
                'openrouter returned empty content')
        try:
            parsed = json.loads(content)
        except ValueError:
            raise ProviderError('bad_response',
                'openrouter returned invalid JSON content')
        if not isinstance(parsed, dict):
            raise ProviderError('bad_response',
                'openrouter structured output is not an object')
        return parsed

    def extract_fields(self, submission_text: str) -> dict[str, Any]:
        """Structured field extraction from submitted content."""
        return self._chat_schema(_EXTRACT_SYSTEM,
            {'submission_text': submission_text}, 'extraction',
            EXTRACTION_SCHEMA)

    def compare_fields(self, extraction: dict[str, Any], context: str,
            evidence: list[dict[str, Any]]) -> dict[str, Any]:
        """Per-field supported/conflicting/not_found verdicts vs evidence."""
        return self._chat_schema(_COMPARE_SYSTEM, {
            'submitted': extraction,
            'submitter_context': context,
            'evidence_pages': evidence,
        }, 'comparison', COMPARISON_SCHEMA)

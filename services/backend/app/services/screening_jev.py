"""TypeSafe Jev adapter — typed judgments (Noul/Choice/Score) over the same
evidence state the OpenRouter comparison sees.

Jev supplies probabilities and confidences; composing them into anything
actionable stays in pipeline code, and no judgment ever maps to a scam/safe
verdict — per spec these are narrow typed answers for the moderator.
"""
import logging
from os import environ
from typing import Any, Protocol

from app.services.providers import ProviderError, ProviderUnavailable

logger = logging.getLogger(__name__)

DEFAULT_MODEL = 'jev-latest'

# The question set is deliberately narrow: corroboration and document
# classification, never a legitimacy verdict.
QUESTION_SPECS: dict[str, dict[str, Any]] = {
    'official_announcement': {
        'type': 'noul',
        'instructions': 'Is the fetched page an official announcement of the '
            'submitted opportunity by the issuing organisation?',
        'criteria': {
            'true': 'The page is published by the issuer and announces this '
                'opportunity',
            'false': 'The page is by someone else, about something else, or '
                'does not announce this opportunity',
        },
    },
    'deadline_corroborated': {
        'type': 'noul',
        'instructions': 'Does the fetched page state the same application '
            'deadline as the submitted details?',
        'criteria': {
            'true': 'The page states a matching deadline',
            'false': 'The page states a different deadline or none at all',
        },
    },
    'doc_kind': {
        'type': 'choice',
        'instructions': 'What kind of document is the fetched page?',
        'criteria': {
            'official_listing': 'Official page of the issuing organisation',
            'aggregator_repost': 'A third-party aggregator or repost',
            'social_post': 'A social-media or chat post',
            'unrelated': 'Not about this opportunity',
            'insufficient_evidence': 'Not enough text to tell',
        },
    },
    'source_authority': {
        'type': 'score',
        'instructions': 'How authoritative is this source for the submitted '
            'opportunity?',
        'criteria': ['Unknown or anonymous source', 'Third-party aggregator',
            'Official issuer channel', 'Verified issuer-operated listing'],
    },
}


def build_questions(*, has_deadline: bool) -> dict[str, Any]:
    """Concrete question objects; deadline noul only when one was submitted."""
    from typesafe_sdk import Choice, Noul, Score
    questions: dict[str, Any] = {}
    for name, spec in QUESTION_SPECS.items():
        if name == 'deadline_corroborated' and not has_deadline:
            continue
        if spec['type'] == 'noul':
            questions[name] = Noul(instructions=spec['instructions'],
                criteria=spec['criteria'])
        elif spec['type'] == 'choice':
            questions[name] = Choice(instructions=spec['instructions'],
                criteria=spec['criteria'])
        else:
            questions[name] = Score(instructions=spec['instructions'],
                criteria=spec['criteria'])
    return questions


def answers_to_json(response: Any) -> dict[str, Any]:
    """Serialize the SDK's typed answers map to plain JSON for result_json."""
    out: dict[str, Any] = {}
    for name, answer in (getattr(response, 'answers', None) or {}).items():
        kind = getattr(answer, 'type', None)
        if kind == 'noul':
            out[name] = {'type': 'noul', 'noul': answer.noul}
        elif kind == 'choice':
            out[name] = {'type': 'choice', 'choice': answer.choice,
                'probabilities': dict(answer.probabilities),
                'confidence': answer.confidence}
        elif kind == 'score':
            out[name] = {'type': 'score', 'score': answer.score,
                'probabilities': dict(answer.probabilities),
                'confidence': answer.confidence,
                'legend': dict(getattr(answer, 'legend', {}) or {})}
    return out


class JevJudge(Protocol):
    def judge(self, state: dict[str, Any], *, has_deadline: bool) -> tuple[
            dict[str, Any], str | None]:
        """Returns (answers-as-json, model_version)."""


class TypeSafeJudge:
    """Synchronous TypeSafe SDK client over TYPESAFE_API_KEY."""

    def __init__(self, *, api_key: str | None = None,
        model: str | None = None, client: Any = None):
        self.api_key = api_key if api_key is not None else environ.get(
            'TYPESAFE_API_KEY', '')
        self.model = model or environ.get('TYPESAFE_MODEL', DEFAULT_MODEL)
        self._client = client

    def judge(self, state: dict[str, Any], *, has_deadline: bool) -> tuple[
            dict[str, Any], str | None]:
        if not self.api_key and self._client is None:
            raise ProviderError('config', 'TYPESAFE_API_KEY is not set')
        if self._client is not None:
            client = self._client
            close = False
        else:
            from typesafe_sdk import RetryPolicy, TypeSafeClient
            client = TypeSafeClient(api_key=self.api_key,
                retry=RetryPolicy(max_retries=2))
            close = True
        try:
            response = client.system_one(state=state,
                questions=build_questions(has_deadline=has_deadline),
                model=self.model)
        except Exception as exc:
            from typesafe_sdk import (TypeSafeAPIConnectionError,
                TypeSafeAPITimeoutError, TypeSafeInternalServerError,
                TypeSafeRateLimitError)
            transient = (TypeSafeAPIConnectionError, TypeSafeAPITimeoutError,
                TypeSafeInternalServerError, TypeSafeRateLimitError)
            if isinstance(exc, transient):
                raise ProviderUnavailable(
                    f'typesafe unavailable: {exc.__class__.__name__}') from exc
            raise ProviderError('http',
                f'typesafe call failed: {exc.__class__.__name__}') from exc
        finally:
            if close:
                closer = getattr(client, 'close', None)
                if closer is not None:
                    closer()
        model_version = getattr(response, 'model', None) or self.model
        return answers_to_json(response), model_version

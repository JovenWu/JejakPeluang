"""Screening pipeline: consume a screening run end to end.

Order: gather submitted content -> OpenRouter field extraction -> Tavily
candidate discovery -> SSRF-hardened fetches -> OpenRouter field comparison
-> TypeSafe Jev judgments -> persist structured result. The pipeline only
produces comparisons and typed judgments for the moderator; it never
publishes and never emits scam/safe verdicts.
"""
import logging
import time
from datetime import datetime, timezone
from os import environ
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalogue import Issuer, IssuerDomain
from app.models.intake import ScreeningRun, Submission, Upload
from app.services.moderation import upload_file_path
from app.services.providers import ProviderError, ProviderUnavailable

logger = logging.getLogger(__name__)

SCHEMA_VERSION = '1'
SUBMISSION_TEXT_CAP = 20_000
LLM_INPUT_CAP = 8_000
EVIDENCE_TEXT_CAP = 4_000
JEV_STATE_EVIDENCE_CAP = 3_000
MAX_CANDIDATE_FETCHES = 3
MAX_EVIDENCE_PAGES = 4
RUN_DEADLINE_SECONDS = 300
AI_MATCH_NOUL_THRESHOLD = 0.6


class Fetcher(Protocol):
    def __call__(self, url: str) -> Any:
        """app.services.fetch.fetch — returns FetchResult or raises FetchError."""


class Searcher(Protocol):
    def search(self, title: str | None, issuer: str | None, *,
            include_domains: list[str] | None = None) -> list[dict[str, Any]]:
        ...


class ExtractorLLM(Protocol):
    def extract_fields(self, submission_text: str) -> dict[str, Any]: ...
    def compare_fields(self, extraction: dict[str, Any], context: str,
            evidence: list[dict[str, Any]]) -> dict[str, Any]: ...


def _extraction_to_jev_evidence(evidence: list[dict[str, Any]]) -> list[dict]:
    pages = []
    for item in evidence:
        text = item.get('text')
        if not text:
            continue
        pages.append({'url': item.get('final_url') or item.get('url'),
            'text': text[:JEV_STATE_EVIDENCE_CAP]})
    return pages


def _gather_submission_text(session: Session, submission: Submission,
        fetcher: Fetcher, errors: list[dict[str, Any]],
        evidence: list[dict[str, Any]]) -> str:
    """Assemble the text the guest gave us: fetched URL text, upload text,
    and the free-text context field."""
    parts: list[str] = []
    if submission.submitted_url:
        item = _fetch_evidence(fetcher, submission.submitted_url,
            origin='submitted_url')
        evidence.append(item)
        if item.get('text'):
            parts.append(item['text'])
    uploads = session.scalars(select(Upload).where(
        Upload.submission_id == submission.id).order_by(
        Upload.storage_key)).all()
    for upload in uploads:
        path = upload_file_path(upload)
        if path is None:
            errors.append({'stage': 'extract', 'kind': 'upload_missing',
                'detail': upload.storage_key})
            continue
        if upload.detected_mime != 'application/pdf':
            errors.append({'stage': 'extract', 'kind': 'unsupported_upload',
                'detail': upload.detected_mime})
            continue
        from app.services.extract import to_text
        text = to_text(path.read_bytes(), 'application/pdf')
        if text:
            parts.append(text)
        else:
            errors.append({'stage': 'extract', 'kind': 'unreadable_upload',
                'detail': upload.storage_key})
    if submission.context:
        parts.append(f'Submitter context:\n{submission.context}')
    return '\n\n'.join(parts)[:SUBMISSION_TEXT_CAP]


def _fetch_evidence(fetcher: Fetcher, url: str, *, origin: str) -> dict[str, Any]:
    """Fetch one URL; never raises — failures land in the evidence record."""
    try:
        result = fetcher(url)
    except Exception as exc:
        kind = getattr(exc, 'kind', exc.__class__.__name__)
        return {'url': url, 'origin': origin, 'fetch_error': str(kind)}
    from app.services.extract import to_text
    return {
        'url': url,
        'origin': origin,
        'final_url': result.final_url,
        'status': result.status,
        'content_type': result.content_type,
        'fetched_at': result.fetched_at.isoformat(),
        'text': to_text(result.content, result.content_type),
    }


def _known_issuer_domains(session: Session, extraction: dict[str, Any],
        submission: Submission) -> list[str]:
    """Verified domains for this issuer, if we already trust some — search
    known issuer domains first per the spec's minimization rule."""
    from urllib.parse import urlsplit
    domains: set[str] = set()
    host = None
    if submission.submitted_url:
        try:
            host = urlsplit(submission.submitted_url).hostname
        except ValueError:
            host = None
    if host:
        row = session.scalar(select(IssuerDomain).where(
            IssuerDomain.domain == host))
        if row is not None:
            domains.add(row.domain)
            issuer = session.get(Issuer, row.issuer_id)
            if issuer is not None:
                for extra in session.scalars(select(IssuerDomain).where(
                        IssuerDomain.issuer_id == issuer.id)):
                    domains.add(extra.domain)
    return sorted(domains)


def _compute_ai_source_match(result: dict[str, Any]) -> bool | None:
    """True when Jev found at least one fetched page it judges to be the
    issuer's official listing of this opportunity; False when evidence exists
    but none qualifies; None when there was nothing to judge.
    """
    pages = result.get('judgments') or []
    if not pages:
        return None
    verdicts = ((result.get('comparison') or {}).get('field_verdicts')
        or {}).values()
    conflicts = any(isinstance(v, dict) and v.get('verdict') == 'conflicting'
        for v in verdicts)
    if conflicts:
        return False
    for page in pages:
        answers = page.get('answers') or {}
        official = (answers.get('official_announcement') or {}).get('noul')
        doc_kind = (answers.get('doc_kind') or {}).get('choice')
        if (official is not None and doc_kind is not None
                and official >= AI_MATCH_NOUL_THRESHOLD
                and doc_kind == 'official_listing'):
            return True
    return False


def _base_result() -> dict[str, Any]:
    return {
        'schema_version': SCHEMA_VERSION,
        'outcome': 'complete',
        'submission_text': None,
        'extraction': None,
        'discovery': {'status': 'skipped', 'query': None, 'results': []},
        'evidence': [],
        'comparison': None,
        'judgments': None,
        'ai_source_match': None,
        'errors': [],
    }


def run_screening(session: Session, run: ScreeningRun, *,
        fetcher: Fetcher | None = None, searcher: Searcher | None = None,
        llm: ExtractorLLM | None = None, judge: Any = None,
        clock=time.monotonic) -> ScreeningRun:
    """Execute one screening run idempotently; owns its state transitions.

    Provider exhaustion degrades the outcome (provider_unavailable /
    manual_review_required / no_public_source) but still completes the run —
    the submission always lands in moderator review. Unexpected exceptions
    mark the run failed and propagate so the outbox can retry.
    """
    submission = session.get(Submission, run.submission_id)
    now = datetime.now(timezone.utc)
    if submission is None:
        run.state = 'failed'
        run.error = 'submission row missing'
        run.finished_at = now
        session.commit()
        return run
    run.state = 'processing'
    run.error = None
    run.attempts = (run.attempts or 0) + 1
    run.started_at = now
    if submission.state in ('queued', 'processing'):
        submission.state = 'processing'
        submission.updated_at = now
    session.flush()
    started = clock()
    result = _base_result()
    outcome = 'complete'
    models: list[str] = []
    providers_used: set[str] = set()

    def deadline_hit() -> bool:
        return clock() - started > RUN_DEADLINE_SECONDS

    try:
        errors = result['errors']
        evidence = result['evidence']
        submission_text = _gather_submission_text(session, submission,
            fetcher, errors, evidence)
        result['submission_text'] = submission_text or None

        extraction = None
        if llm is not None and submission_text:
            providers_used.add('openrouter')
            try:
                extraction = llm.extract_fields(submission_text[:LLM_INPUT_CAP])
                result['extraction'] = extraction
                models.append(getattr(llm, 'model', 'openrouter'))
            except ProviderUnavailable as exc:
                errors.append({'stage': 'extract', 'kind': exc.kind,
                    'detail': exc.detail})
                outcome = 'provider_unavailable'
            except ProviderError as exc:
                errors.append({'stage': 'extract', 'kind': exc.kind,
                    'detail': exc.detail})
                outcome = 'manual_review_required'
        elif not submission_text:
            outcome = 'no_content'
        else:
            errors.append({'stage': 'extract', 'kind': 'not_configured',
                'detail': 'no extraction provider configured'})
            outcome = 'provider_unavailable'

        if extraction:
            domains = _known_issuer_domains(session, extraction, submission)
            if searcher is not None and not deadline_hit():
                providers_used.add('tavily')
                result['discovery'] = _discover(searcher, extraction,
                    domains, errors)
                for candidate in result['discovery']['results']:
                    if len(evidence) >= MAX_EVIDENCE_PAGES or deadline_hit():
                        break
                    url = candidate['url']
                    if any(url in (e.get('url'), e.get('final_url'))
                            for e in evidence):
                        continue
                    evidence.append(_fetch_evidence(fetcher, url,
                        origin='tavily'))

        has_text_evidence = any(e.get('text') for e in evidence)
        if extraction and has_text_evidence and not deadline_hit():
            capped = [{**e, 'text': (e.get('text') or '')[:EVIDENCE_TEXT_CAP]}
                for e in evidence if e.get('text')]
            try:
                result['comparison'] = llm.compare_fields(extraction,
                    submission.context or '', capped)
            except ProviderUnavailable as exc:
                errors.append({'stage': 'compare', 'kind': exc.kind,
                    'detail': exc.detail})
                outcome = 'provider_unavailable'
            except ProviderError as exc:
                errors.append({'stage': 'compare', 'kind': exc.kind,
                    'detail': exc.detail})
                outcome = 'manual_review_required'
        elif extraction and not has_text_evidence:
            if outcome == 'complete':
                outcome = 'no_public_source'

        if (judge is not None and has_text_evidence and extraction
                and not deadline_hit()):
            pages = _extraction_to_jev_evidence(evidence)
            judgments: list[dict[str, Any]] = []
            jev_model = None
            for page in pages:
                if deadline_hit():
                    errors.append({'stage': 'judge',
                        'kind': 'deadline_exceeded',
                        'detail': 'run deadline hit mid-judging'})
                    break
                state = {'submitted': extraction,
                    'submitter_context': submission.context or '',
                    'evidence': [page]}
                try:
                    providers_used.add('typesafe-jev')
                    answers, jev_model = judge.judge(state,
                        has_deadline=bool(extraction.get('deadline')))
                except ProviderUnavailable as exc:
                    errors.append({'stage': 'judge', 'kind': exc.kind,
                        'detail': exc.detail})
                    if outcome == 'complete':
                        outcome = 'provider_unavailable'
                    break
                except ProviderError as exc:
                    errors.append({'stage': 'judge', 'kind': exc.kind,
                        'detail': exc.detail})
                    break
                judgments.append({'url': page['url'], 'answers': answers})
            result['judgments'] = judgments or None
            if jev_model:
                models.append(jev_model)
        elif judge is None:
            errors.append({'stage': 'judge', 'kind': 'not_configured',
                'detail': 'no Jev judge configured'})

        result['ai_source_match'] = _compute_ai_source_match(result)
        result['outcome'] = outcome
        finished = datetime.now(timezone.utc)
        run.state = 'complete'
        run.result_json = result
        run.provider_version = ('+'.join(sorted(providers_used)) or None)
        run.model_version = '+'.join(models)[:64] or None
        run.schema_version = SCHEMA_VERSION
        run.finished_at = finished
    except Exception as exc:
        run.state = 'failed'
        run.error = str(exc)[:255]
        run.finished_at = datetime.now(timezone.utc)
        if submission.state in ('queued', 'processing'):
            submission.state = 'review_pending'
            submission.updated_at = run.finished_at
        session.commit()
        raise
    if submission.state in ('queued', 'processing'):
        submission.state = 'review_pending'
        submission.updated_at = run.finished_at
    session.commit()
    return run


def _discover(searcher: Searcher, extraction: dict[str, Any],
        domains: list[str], errors: list[dict[str, Any]]) -> dict[str, Any]:
    """Tavily discovery: minimized title+issuer query, issuer domains first."""
    from app.services.screening_tavily import minimized_query
    query = minimized_query(extraction.get('title'), extraction.get('issuer'))
    discovery = {'status': 'skipped', 'query': query or None, 'results': []}
    if not query:
        return discovery
    attempts = ([{'include_domains': domains}, {}] if domains else [{}])
    for kwargs in attempts:
        try:
            candidates = searcher.search(extraction.get('title'),
                extraction.get('issuer'), **kwargs)
        except ProviderError as exc:
            errors.append({'stage': 'discover', 'kind': exc.kind,
                'detail': exc.detail})
            discovery['status'] = 'provider_unavailable'
            return discovery
        if candidates:
            discovery['status'] = 'ok'
            discovery['results'] = [
                {'url': c['url'], 'title': c.get('title', '')}
                for c in candidates[:MAX_CANDIDATE_FETCHES + 2]
                if isinstance(c.get('url'), str)
                and c['url'].startswith(('http://', 'https://'))]
            return discovery
    discovery['status'] = 'no_results'
    return discovery


def default_clients() -> tuple:
    """Real clients wired from env; returns (fetcher, searcher, llm, judge)."""
    from app.services.fetch import fetch
    from app.services.screening_jev import TypeSafeJudge
    from app.services.screening_openrouter import OpenRouterClient
    from app.services.screening_tavily import TavilySearcher
    return (fetch, TavilySearcher(), OpenRouterClient(),
        TypeSafeJudge() if environ.get('TYPESAFE_API_KEY') else None)

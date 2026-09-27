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
from urllib.parse import urlsplit

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.catalogue import Issuer, IssuerDomain
from app.models.intake import ScreeningRun, Submission, Upload
from app.services.moderation import upload_file_path
from app.services.providers import ProviderError, ProviderUnavailable
from app.services.screening_assessment import (build_evidence_confidence,
    build_site_assessment)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = '2'
SUBMISSION_TEXT_CAP = 20_000
LLM_INPUT_CAP = 8_000
EVIDENCE_TEXT_CAP = 4_000
JEV_STATE_EVIDENCE_CAP = 3_000
MAX_CANDIDATE_FETCHES = 3
MAX_EVIDENCE_PAGES = 4
MAX_QR_PREFETCHES = 1
MAX_QR_CODES = 6
MAX_SOURCE_MEDIA_IMAGES = 3
MAX_DISCOVERY_RESULTS = 8
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


def _record_media_error(errors: list[dict[str, Any]], kind: str,
        origin: str) -> None:
    if not any(error.get('stage') == 'extract' and error.get('kind') == kind
            for error in errors):
        errors.append({'stage': 'extract', 'kind': kind, 'detail': origin})


def _inspect_media_content(content: bytes, content_type: str | None, *,
        origin: str, qr_codes: list[dict[str, Any]],
        errors: list[dict[str, Any]],
        source_image: str | None = None) -> list[str]:
    media = (content_type or '').split(';', 1)[0].strip().lower()
    from app.services.media import MAX_PDF_IMAGES, inspect_image, pdf_image_bytes
    if media == 'application/pdf' or content.startswith(b'%PDF-'):
        images = pdf_image_bytes(content)
    elif media.startswith('image/'):
        images = [content]
    else:
        return []
    text_parts: list[str] = []
    for image in images[:MAX_PDF_IMAGES]:
        text, urls, error = inspect_image(image)
        if text:
            text_parts.append(text)
        if error:
            _record_media_error(errors, error, origin)
        for url in urls:
            if (len(qr_codes) >= MAX_QR_CODES
                    or any(code.get('url') == url for code in qr_codes)):
                continue
            code = {'url': url, 'origin': origin}
            if source_image:
                code['image_url'] = source_image
            qr_codes.append(code)
    return text_parts


def _gather_submission_text(session: Session, submission: Submission,
        fetcher: Fetcher, errors: list[dict[str, Any]],
        evidence: list[dict[str, Any]], *, media_urls: list[str],
        qr_codes: list[dict[str, Any]]) -> str:
    """Assemble the text the guest gave us: fetched URL text, upload text,
    and the free-text context field."""
    parts: list[str] = []
    if submission.submitted_url:
        item = _fetch_evidence(fetcher, submission.submitted_url,
            origin='submitted_url', media_urls=media_urls,
            qr_codes=qr_codes, errors=errors)
        evidence.append(item)
        if item.get('text'):
            parts.append(item['text'])
        elif item.get('extract_error'):
            errors.append({'stage': 'extract', 'kind': item['extract_error'],
                'detail': submission.submitted_url})
    uploads = session.scalars(select(Upload).where(
        Upload.submission_id == submission.id).order_by(
        Upload.storage_key)).all()
    for upload in uploads:
        path = upload_file_path(upload)
        if path is None:
            errors.append({'stage': 'extract', 'kind': 'upload_missing',
                'detail': upload.storage_key})
            continue
        if upload.detected_mime not in ('application/pdf', 'image/jpeg',
                'image/png'):
            errors.append({'stage': 'extract', 'kind': 'unsupported_upload',
                'detail': upload.detected_mime})
            continue
        content = path.read_bytes()
        from app.services.extract import to_text
        text = to_text(content, upload.detected_mime)
        media_text = _inspect_media_content(content, upload.detected_mime,
            origin='uploaded_file', qr_codes=qr_codes, errors=errors)
        combined = '\n\n'.join(value for value in [text, *media_text] if value)
        if combined:
            parts.append(combined)
        else:
            errors.append({'stage': 'extract', 'kind': 'unreadable_upload',
                'detail': upload.storage_key})
    if submission.context:
        parts.append(f'Submitter context:\n{submission.context}')
    return '\n\n'.join(parts)[:SUBMISSION_TEXT_CAP]


def _fetch_evidence(fetcher: Fetcher, url: str, *, origin: str,
        media_urls: list[str] | None = None,
        qr_codes: list[dict[str, Any]] | None = None,
        errors: list[dict[str, Any]] | None = None,
        source_image: str | None = None) -> dict[str, Any]:
    """Fetch one URL; never raises — failures land in the evidence record."""
    try:
        result = fetcher(url)
    except Exception as exc:
        kind = getattr(exc, 'kind', exc.__class__.__name__)
        return {'url': url, 'origin': origin, 'fetch_error': str(kind)}
    from app.services.extract import page_text
    text, extract_error = page_text(result.content, result.content_type)
    media = (result.content_type or '').split(';', 1)[0].strip().lower()
    if media in ('text/html', 'application/xhtml+xml') and media_urls is not None:
        from app.services.media import image_urls_from_html
        for image_url in image_urls_from_html(result.content,
                result.final_url):
            if image_url not in media_urls and len(media_urls) < MAX_SOURCE_MEDIA_IMAGES:
                media_urls.append(image_url)
    if qr_codes is not None and errors is not None:
        media_text = _inspect_media_content(result.content,
            result.content_type, origin=origin, qr_codes=qr_codes,
            errors=errors, source_image=source_image)
        if media_text:
            text = '\n\n'.join(value for value in [text, *media_text] if value)
            extract_error = None
    item = {
        'url': url,
        'origin': origin,
        'final_url': result.final_url,
        'status': result.status,
        'content_type': result.content_type,
        'fetched_at': result.fetched_at.isoformat(),
        'text': text,
    }
    if getattr(result, 'rendered', False):
        item['rendered'] = True
    if extract_error:
        item['extract_error'] = extract_error
    return item


def _known_issuer_domains(session: Session, extraction: dict[str, Any],
        submission: Submission) -> list[str]:
    """Verified domains for this issuer, if we already trust some — search
    known issuer domains first per the spec's minimization rule."""
    issuer_ids = set()
    name = extraction.get('issuer')
    normalized_name = name.strip().lower() if isinstance(name, str) else ''
    if submission.submitted_url:
        try:
            host = urlsplit(submission.submitted_url).hostname
        except ValueError:
            host = None
        if host:
            row = session.scalar(select(IssuerDomain).where(
                IssuerDomain.domain == host))
            issuer = session.get(Issuer, row.issuer_id) if row is not None else None
            if (issuer is not None and normalized_name
                    and issuer.name.strip().lower() == normalized_name):
                issuer_ids.add(issuer.id)
    if normalized_name:
        issuer = session.scalar(select(Issuer).where(
            func.lower(Issuer.name) == normalized_name))
        if issuer is not None:
            issuer_ids.add(issuer.id)
    if not issuer_ids:
        return []
    domains = session.scalars(select(IssuerDomain).where(
        IssuerDomain.issuer_id.in_(issuer_ids)))
    return sorted({domain.domain for domain in domains})


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


def _scan_remote_images(fetcher: Fetcher, media_urls: list[str],
        qr_codes: list[dict[str, Any]],
        errors: list[dict[str, Any]]) -> str:
    from app.services.media import MAX_IMAGE_URLS
    text_parts: list[str] = []
    for url in media_urls[:min(MAX_SOURCE_MEDIA_IMAGES, MAX_IMAGE_URLS)]:
        item = _fetch_evidence(fetcher, url, origin='submitted_media',
            qr_codes=qr_codes, errors=errors, source_image=url)
        if item.get('fetch_error'):
            kind = item['fetch_error']
            if not any(error.get('stage') == 'qr_scan'
                    and error.get('kind') == kind for error in errors):
                errors.append({'stage': 'qr_scan', 'kind': kind,
                    'detail': url})
            continue
        media = (item.get('content_type') or '').split(';', 1)[0].lower()
        if media.startswith('image/') and item.get('text'):
            text_parts.append('[OCR dari gambar pada tautan kiriman]\n'
                + item['text'])
    return '\n\n'.join(text_parts)[:SUBMISSION_TEXT_CAP]


def _fetch_qr_pages(fetcher: Fetcher, qr_codes: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        errors: list[dict[str, Any]]) -> list[str]:
    parts: list[str] = []
    inspected = 0
    for code in list(qr_codes):
        if inspected >= MAX_QR_PREFETCHES or len(evidence) >= MAX_EVIDENCE_PAGES:
            break
        url = code['url']
        if any(url in (item.get('url'), item.get('final_url'))
                for item in evidence):
            continue
        item = _fetch_evidence(fetcher, url, origin='qr_code',
            qr_codes=qr_codes, errors=errors)
        evidence.append(item)
        inspected += 1
        if item.get('text'):
            parts.append('[Teks dari tujuan tautan QR; perlu pemeriksaan sumber]\n'
                + item['text'])
    return parts


def _safe_candidate_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        return None
    try:
        parts = urlsplit(value.strip())
        port = parts.port
    except ValueError:
        return None
    if (parts.scheme not in ('http', 'https') or not parts.hostname
            or parts.username is not None or parts.password is not None
            or port not in (None, 80, 443)):
        return None
    return value.strip()


def _base_result() -> dict[str, Any]:
    return {
        'schema_version': SCHEMA_VERSION,
        'outcome': 'complete',
        'submission_text': None,
        'extraction': None,
        'extraction_origin': None,
        'discovery': {'status': 'skipped', 'query': None, 'results': []},
        'evidence': [],
        'qr_codes': [],
        'comparison': None,
        'judgments': None,
        'ai_source_match': None,
        'site_assessment': None,
        'confidence': None,
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
        qr_codes = result['qr_codes']
        media_urls: list[str] = []
        submission_text = _gather_submission_text(session, submission,
            fetcher, errors, evidence, media_urls=media_urls,
            qr_codes=qr_codes)
        image_text = _scan_remote_images(fetcher, media_urls, qr_codes, errors)
        if image_text:
            submission_text = '\n\n'.join(value for value in
                (submission_text, image_text) if value)[:SUBMISSION_TEXT_CAP]
        qr_text = _fetch_qr_pages(fetcher, qr_codes, evidence, errors)
        extraction_text = '\n\n'.join(value for value in
            (submission_text, *qr_text) if value)[:SUBMISSION_TEXT_CAP]
        if qr_text:
            result['extraction_origin'] = ('submitted_material_and_qr'
                if submission_text else 'qr_destination')
        elif submission_text:
            result['extraction_origin'] = 'submitted_material'
        result['submission_text'] = extraction_text or None

        extraction = None
        domains: list[str] = []
        if llm is not None and extraction_text:
            providers_used.add('openrouter')
            try:
                extraction = llm.extract_fields(extraction_text[:LLM_INPUT_CAP])
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
        elif not extraction_text:
            outcome = 'no_content'
        else:
            errors.append({'stage': 'extract', 'kind': 'not_configured',
                'detail': 'no extraction provider configured'})
            outcome = 'provider_unavailable'

        if extraction:
            domains = _known_issuer_domains(session, extraction, submission)
            extra_candidates = [
                {'url': code.get('url'), 'title': 'Tautan dari kode QR',
                    'purpose': 'qr_code'} for code in qr_codes]
            for field, title, purpose in (
                    ('application_url', 'Tautan pendaftaran', 'application_url'),
                    ('source_hint', 'Sumber yang disebut di kiriman', 'source_hint')):
                url = _safe_candidate_url(extraction.get(field))
                if url:
                    extra_candidates.append({'url': url, 'title': title,
                        'purpose': purpose})
            if not deadline_hit():
                if searcher is not None:
                    providers_used.add('tavily')
                result['discovery'] = _discover(searcher, extraction,
                    domains, errors, extra_candidates)
                candidate_fetches = 0
                for candidate in result['discovery']['results']:
                    if (len(evidence) >= MAX_EVIDENCE_PAGES
                            or candidate_fetches >= MAX_CANDIDATE_FETCHES
                            or deadline_hit()):
                        break
                    url = candidate['url']
                    if any(url in (item.get('url'), item.get('final_url'))
                            for item in evidence):
                        continue
                    evidence.append(_fetch_evidence(fetcher, url,
                        origin=candidate['purpose'], qr_codes=qr_codes,
                        errors=errors))
                    candidate_fetches += 1

        has_text_evidence = any(item.get('text') for item in evidence)
        if extraction and has_text_evidence and not deadline_hit():
            capped = [{**item, 'text': (item.get('text') or '')[:EVIDENCE_TEXT_CAP]}
                for item in evidence if item.get('text')]
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
                    'issuer_name': extraction.get('issuer'),
                    'known_issuer_domains': domains,
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
        result['site_assessment'] = build_site_assessment(result, domains)
        result['confidence'] = build_evidence_confidence(extraction,
            result['comparison'], result['site_assessment'])
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


def _discover(searcher: Searcher | None, extraction: dict[str, Any],
        domains: list[str], errors: list[dict[str, Any]],
        extra_candidates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Tavily discovery: minimized title+issuer query, issuer domains first."""
    from app.services.screening_tavily import minimized_query
    issuer = extraction.get('issuer')
    searches = [('opportunity', extraction.get('title'), issuer)]
    if isinstance(issuer, str) and issuer.strip():
        searches.append(('issuer_website', 'situs resmi', issuer))
    queries = [minimized_query(title, name) for _, title, name in searches]
    queries = [query for query in queries if query]
    discovery = {'status': 'skipped',
        'query': ' · '.join(queries) or None, 'results': []}
    results: list[dict[str, Any]] = []

    def add(url: Any, title: Any, purpose: str) -> None:
        candidate = _safe_candidate_url(url)
        if (candidate and not any(item['url'] == candidate for item in results)
                and len(results) < MAX_DISCOVERY_RESULTS):
            results.append({'url': candidate,
                'title': title if isinstance(title, str) else '',
                'purpose': purpose})

    for candidate in extra_candidates or []:
        add(candidate.get('url'), candidate.get('title'),
            candidate.get('purpose', 'submitted_link'))
    if searcher is None or not queries:
        discovery['status'] = 'ok' if results else 'skipped'
        discovery['results'] = results
        return discovery

    searched = False
    search_results = False
    failed = False
    for purpose, title, name in searches:
        query = minimized_query(title, name)
        if not query:
            continue
        attempts = ([{'include_domains': domains}, {}]
            if domains else [{}])
        for kwargs in attempts:
            try:
                candidates = searcher.search(title, name, **kwargs)
            except ProviderError as exc:
                errors.append({'stage': 'discover', 'kind': exc.kind,
                    'detail': exc.detail})
                failed = True
                break
            searched = True
            if candidates:
                search_results = True
                for candidate in candidates:
                    if isinstance(candidate, dict):
                        add(candidate.get('url'), candidate.get('title'),
                            purpose)
                break
        if failed:
            break
    if failed:
        discovery['status'] = 'partial' if results else 'provider_unavailable'
    elif search_results or results:
        discovery['status'] = 'ok'
    elif searched:
        discovery['status'] = 'no_results'
    discovery['results'] = results
    return discovery


def default_clients() -> tuple:
    """Real clients wired from env; returns (fetcher, searcher, llm, judge)."""
    from app.services.fetch import fetch
    from app.services.render_client import with_rendering
    from app.services.screening_jev import TypeSafeJudge
    from app.services.screening_openrouter import OpenRouterClient
    from app.services.screening_tavily import TavilySearcher
    return (with_rendering(fetch), TavilySearcher(), OpenRouterClient(),
        TypeSafeJudge() if environ.get('TYPESAFE_API_KEY') else None)

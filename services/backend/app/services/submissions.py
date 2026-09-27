import hashlib
import ipaddress
import re
import secrets
import socket
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from os import environ
from pathlib import Path
from typing import BinaryIO, Protocol
from urllib.parse import (parse_qsl, urlencode, urlsplit, urlunsplit)
from uuid import uuid4

from pypdf import PdfReader
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.catalogue import ModerationDecision, Opportunity
from app.models.intake import JobOutbox, ScreeningRun, Submission, Upload

MAX_FILES = 3
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 15
CHUNK_BYTES = 256 * 1024
RETENTION_DAYS = 30
REF_PREFIX = 'JP-'
REF_LENGTH = 8
CROCKFORD_ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'
OUTBOX_EVENT = 'screening.requested'
MAX_URL_LENGTH = 2048
MAX_EMAIL_LENGTH = 320
MAX_CONTEXT_LENGTH = 4096

_HOST_LABEL = r'[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?'
_HOST_RE = re.compile(rf'{_HOST_LABEL}(\.{_HOST_LABEL})*')
_EMAIL_RE = re.compile(r'[^@\s]+@[^@\s]+\.[^@\s]+')

STATUS_LABELS = {
    'received': 'Diterima',
    'queued': 'Dalam antrean',
    'processing': 'Sedang diproses',
    'review_pending': 'Menunggu peninjauan moderator',
    'published': 'Dipublikasikan',
    'closed_unreviewed': 'Ditutup tanpa peninjauan',
}
DEFAULT_STATUS_LABEL = 'Ditutup'


class SubmissionError(Exception):
    """Domain rejection; the API layer maps it to HTTPException."""

    def __init__(self, status_code: int, detail):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class FileScanner(Protocol):
    """Antivirus seam: raises on detection. NoOpScanner is the default."""

    def scan(self, path: Path) -> None:
        ...


class NoOpScanner:
    def scan(self, path: Path) -> None:
        return None


def get_scanner() -> FileScanner:
    return NoOpScanner()


def upload_root() -> Path:
    return Path(environ.get('UPLOAD_DIR', './uploads'))


def _staging_dir() -> Path:
    return upload_root() / 'staging'


@dataclass
class StagedUpload:
    staged_path: Path
    final_path: Path
    storage_key: str
    detected_mime: str
    size_bytes: int
    sha256: str
    page_count: int | None
    finalized: bool = False


def _is_ip_literal(host: str) -> bool:
    """True when host is an IP literal, including hex/octal/integer IPv4
    encodings that resolvers treat as addresses (e.g. ``0x7f.0.0.1``,
    ``2130706433``)."""
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    try:
        socket.inet_aton(host)
        return True
    except OSError:
        return False


def validate_url(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    candidate = raw.strip()
    if len(candidate) > MAX_URL_LENGTH:
        raise SubmissionError(422, 'url is too long')
    try:
        parts = urlsplit(candidate)
    except ValueError:
        raise SubmissionError(422, 'url is malformed')
    if parts.scheme not in ('http', 'https'):
        raise SubmissionError(422, 'url must use http or https')
    if parts.username is not None or parts.password is not None:
        raise SubmissionError(422, 'url must not embed credentials')
    try:
        port = parts.port
    except ValueError:
        raise SubmissionError(422, 'url port is invalid')
    if port not in (None, 80, 443):
        raise SubmissionError(422, 'url port must be 80 or 443')
    host = parts.hostname
    if not host:
        raise SubmissionError(422, 'url host is not a valid domain')
    if _is_ip_literal(host):
        raise SubmissionError(422, 'url host must be a domain, not an IP')
    if not _HOST_RE.fullmatch(host):
        raise SubmissionError(422, 'url host is not a valid domain')
    return candidate


def validate_contact_email(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    candidate = raw.strip()
    if len(candidate) > MAX_EMAIL_LENGTH or not _EMAIL_RE.fullmatch(candidate):
        raise SubmissionError(422, 'contact_email is invalid')
    return candidate


def _detect_type(path: Path) -> tuple[str, str] | None:
    with path.open('rb') as handle:
        head = handle.read(8)
    if head.startswith(b'%PDF-'):
        return 'application/pdf', '.pdf'
    if head.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg', '.jpg'
    if head.startswith(b'\x89PNG'):
        return 'image/png', '.png'
    return None


def _pdf_page_count(path: Path) -> int:
    try:
        return len(PdfReader(str(path)).pages)
    except Exception:
        raise SubmissionError(400, 'PDF file could not be parsed')


def _stream_to_staging(source: BinaryIO, staged_path: Path,
        total_so_far: int) -> tuple[int, str]:
    hasher = hashlib.sha256()
    size = 0
    with staged_path.open('wb') as out:
        while chunk := source.read(CHUNK_BYTES):
            size += len(chunk)
            if size > MAX_FILE_BYTES:
                raise SubmissionError(413,
                    'Each file must be at most 10 MB')
            if total_so_far + size > MAX_TOTAL_BYTES:
                raise SubmissionError(413,
                    'Combined files must be at most 20 MB')
            hasher.update(chunk)
            out.write(chunk)
    return size, hasher.hexdigest()


def _cleanup(staged: list[StagedUpload]) -> None:
    for item in staged:
        target = item.final_path if item.finalized else item.staged_path
        target.unlink(missing_ok=True)


def stage_files(files, scanner: FileScanner) -> list[StagedUpload]:
    """Stream uploads to staging, enforce caps, sniff magic, scan.

    Files land under ``<UPLOAD_DIR>/staging`` first (never under their client
    filename); on any failure everything staged so far is deleted.
    """
    staging = _staging_dir()
    staging.mkdir(parents=True, exist_ok=True)
    staged: list[StagedUpload] = []
    total = 0
    in_progress: Path | None = None
    try:
        for upload in files:
            staged_path = staging / f'{uuid4().hex}.part'
            in_progress = staged_path
            size, digest = _stream_to_staging(upload.file, staged_path, total)
            total += size
            detected = _detect_type(staged_path)
            if detected is None:
                raise SubmissionError(400,
                    'Unsupported file type (expected PDF, JPEG, or PNG)')
            mime, ext = detected
            page_count = None
            if mime == 'application/pdf':
                page_count = _pdf_page_count(staged_path)
                if page_count > MAX_PDF_PAGES:
                    raise SubmissionError(400,
                        'PDF files may have at most 15 pages')
            try:
                scanner.scan(staged_path)
            except SubmissionError:
                raise
            except Exception:
                raise SubmissionError(400, 'File rejected by scanner')
            storage_key = f'{uuid4().hex}{ext}'
            staged.append(StagedUpload(staged_path=staged_path,
                final_path=upload_root() / storage_key, storage_key=storage_key,
                detected_mime=mime, size_bytes=size, sha256=digest,
                page_count=page_count))
            in_progress = None
    except Exception:
        if in_progress is not None:
            in_progress.unlink(missing_ok=True)
        _cleanup(staged)
        raise
    return staged


TRACKING_PARAMS = frozenset({'fbclid', 'gclid', 'igshid'})


def normalize_url(raw: str | None) -> str | None:
    """Canonical URL for dedupe comparison: lowercase scheme/host, default
    port stripped, fragment and tracking params dropped, no trailing
    slash."""
    if not raw:
        return None
    try:
        parts = urlsplit(raw.strip())
        host = (parts.hostname or '').lower()
        port = parts.port
    except ValueError:
        return None
    if not host:
        return None
    scheme = parts.scheme.lower() or 'https'
    netloc = host + (f':{port}' if port and port not in (80, 443) else '')
    path = parts.path.rstrip('/') or '/'
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query)
        if not k.lower().startswith('utm_')
        and k.lower() not in TRACKING_PARAMS))
    return urlunsplit((scheme, netloc, path, query, ''))


def find_duplicate(session: Session, url: str | None) -> dict | None:
    """Normalized-URL match against public rows: any opportunity's
    source_url wins first, then a review_pending submission. Queued or
    terminal submissions are ignored — decided content stays checkable via
    the listing, and an in-flight queue window is too small to block on."""
    target = normalize_url(url)
    if target is None:
        return None
    for opportunity in session.scalars(select(Opportunity).where(
            Opportunity.source_url.is_not(None))):
        if normalize_url(opportunity.source_url) == target:
            return {'kind': 'listing', 'slug': opportunity.slug,
                'title': opportunity.title, 'status': opportunity.status}
    pending = session.scalars(select(Submission).where(
        Submission.state == 'review_pending',
        Submission.submitted_url.is_not(None)))
    for submission in pending:
        if normalize_url(submission.submitted_url) == target:
            return {'kind': 'incoming', 'ref': submission.ref,
                'screening': screening_projection(
                    _latest_run(session, submission))}
    return None


def _new_ref(session: Session) -> str:
    for _ in range(10):
        ref = REF_PREFIX + ''.join(
            secrets.choice(CROCKFORD_ALPHABET) for _ in range(REF_LENGTH))
        exists = session.scalar(
            select(Submission.id).where(Submission.ref == ref))
        if not exists:
            return ref
    raise SubmissionError(500, 'Could not allocate a submission reference')


def intake_submission(session: Session, *, url, context, contact_email, files,
        client_net: str, scanner: FileScanner) -> tuple[Submission, str]:
    """Validate, stage, and persist a guest submission in one transaction."""
    submitted_url = validate_url(url)
    email = validate_contact_email(contact_email)
    context = context or ''
    if len(context) > MAX_CONTEXT_LENGTH:
        raise SubmissionError(422,
            f'context exceeds {MAX_CONTEXT_LENGTH} characters')
    uploads = [f for f in files if f.filename]
    if not submitted_url and not uploads:
        raise SubmissionError(422, 'Provide a url or at least one file')
    if submitted_url:
        duplicate = find_duplicate(session, submitted_url)
        if duplicate is not None:
            raise SubmissionError(409, {'error': 'duplicate', **duplicate})
    if len(uploads) > MAX_FILES:
        raise SubmissionError(422, 'At most 3 files per submission')
    staged = stage_files(uploads, scanner)
    try:
        upload_root().mkdir(parents=True, exist_ok=True)
        for item in staged:
            item.staged_path.replace(item.final_path)
            item.finalized = True
        now = datetime.now(timezone.utc)
        purge_after = now + timedelta(days=RETENTION_DAYS)
        receipt_token = secrets.token_urlsafe(32)
        submission = Submission(ref=_new_ref(session),
            receipt_token_hash=hashlib.sha256(
                receipt_token.encode()).hexdigest(),
            submitted_url=submitted_url, context=(context or '').strip(),
            contact_email=email, state='received', client_net_hash=client_net,
            purge_after=purge_after, created_at=now, updated_at=now)
        session.add(submission)
        session.flush()
        for item in staged:
            session.add(Upload(submission_id=submission.id,
                storage_key=item.storage_key,
                detected_mime=item.detected_mime, size_bytes=item.size_bytes,
                page_count=item.page_count, sha256=item.sha256,
                delete_after=purge_after))
        run = ScreeningRun(submission_id=submission.id, state='queued',
            created_at=now)
        session.add(run)
        session.flush()
        session.add(JobOutbox(event_type=OUTBOX_EVENT,
            screening_run_id=run.id, created_at=now))
        submission.state = 'queued'
        session.commit()
    except Exception:
        try:
            session.rollback()
        finally:
            # File cleanup must run even if rollback itself fails, or
            # finalized uploads would be orphaned on disk.
            _cleanup(staged)
        raise
    return submission, receipt_token


def _official_per_url(result: dict) -> dict[str, bool | None]:
    """Map each judged evidence URL to its official-listing verdict."""
    official: dict[str, bool | None] = {}
    for page in result.get('judgments') or []:
        answers = page.get('answers') or {}
        noul = (answers.get('official_announcement') or {}).get('noul')
        doc_kind = (answers.get('doc_kind') or {}).get('choice')
        if noul is None and doc_kind is None:
            official[page.get('url')] = None
        else:
            official[page.get('url')] = bool(
                noul is not None and doc_kind is not None
                and noul >= 0.6 and doc_kind == 'official_listing')
    return official


def _public_source_url(item: dict) -> str | None:
    url = item.get('final_url') or item.get('url')
    if not isinstance(url, str) or item.get('origin') != 'qr_code':
        return url
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    return urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))


def _public_sources(result: dict) -> list[dict]:
    """Fetched evidence pages, minus body text — safe for public display."""
    official = _official_per_url(result)
    sources = []
    for item in result.get('evidence') or []:
        if item.get('origin') == 'submitted_media':
            continue
        url = _public_source_url(item)
        if not url:
            continue
        sources.append({'url': url, 'status': item.get('status'),
            'official': official.get(item.get('url'), official.get(
                item.get('final_url'))),
            'error': item.get('extract_error') or item.get('fetch_error'),
            'origin': item.get('origin')})
    return sources


def _public_extraction(raw: object) -> dict | None:
    if not isinstance(raw, dict):
        return None
    fields = ('title', 'issuer', 'deadline', 'category', 'region',
        'description', 'eligibility', 'fees', 'requested_data')
    return {field: raw[field] for field in fields if field in raw}


def _public_site_assessment(raw: object) -> dict | None:
    if not isinstance(raw, dict):
        return None
    return {
        'status': raw.get('status', 'inconclusive'),
        'issuer_website_candidates': len(raw.get('issuer_websites') or []),
        'social_sources': len(raw.get('social_sources') or []),
        'third_party_sources': len(raw.get('third_party_sources') or []),
        'unclassified_sources': len(raw.get('unclassified_sources') or []),
        'qr_codes_found': raw.get('qr_codes_found', 0),
    }


def screening_projection(run: ScreeningRun | None) -> dict | None:
    """Guest/public-safe view of a screening run.

    Everything in it is either the submitter's own extracted data or public
    web facts (source URLs, field verdicts). It deliberately omits
    submission_text, evidence body text, provider internals, PII, and any
    verdict language — the AI reports what it found, never 'safe'/'scam'.
    """
    if run is None:
        return None
    projection: dict = {'state': run.state, 'outcome': None,
        'extracted': None, 'field_verdicts': None, 'sources': [],
        'ai_source_match': None, 'confidence': None,
        'site_assessment': None, 'errors': [],
        'finished_at': run.finished_at}
    result = run.result_json if isinstance(run.result_json, dict) else None
    if result is None:
        return projection
    projection['outcome'] = result.get('outcome')
    projection['extracted'] = _public_extraction(result.get('extraction'))
    projection['field_verdicts'] = ((result.get('comparison') or {})
        .get('field_verdicts'))
    projection['sources'] = _public_sources(result)
    projection['ai_source_match'] = result.get('ai_source_match')
    projection['confidence'] = result.get('confidence')
    projection['site_assessment'] = _public_site_assessment(
        result.get('site_assessment'))
    projection['errors'] = [{'stage': e.get('stage'), 'kind': e.get('kind')}
        for e in result.get('errors') or [] if isinstance(e, dict)]
    return projection


def _latest_run(session: Session,
        submission: Submission) -> ScreeningRun | None:
    return session.scalar(select(ScreeningRun).where(
        ScreeningRun.submission_id == submission.id).order_by(
        ScreeningRun.created_at.desc()).limit(1))


def status_view(session: Session, submission: Submission) -> dict:
    decision = session.scalar(select(ModerationDecision).where(
        ModerationDecision.submission_id == submission.id).order_by(
        ModerationDecision.decided_at.desc()).limit(1))
    return {
        'ref': submission.ref,
        'state': submission.state,
        'status_label': STATUS_LABELS.get(submission.state,
            DEFAULT_STATUS_LABEL),
        'created_at': submission.created_at,
        'decision': decision.status if decision else None,
        'needs_more_evidence': bool(
            decision and decision.status == 'needs_more_evidence'),
        'screening': screening_projection(
            _latest_run(session, submission)),
    }


def list_incoming(session: Session, *, limit: int,
        offset: int) -> tuple[list[dict], int]:
    """Public feed of AI-checked submissions awaiting moderator review —
    newest first. Sanitized like screening_projection: no context, PII,
    uploads, or client identifiers ever leave this function."""
    statement = select(Submission).where(
        Submission.state == 'review_pending')
    total = session.scalar(
        select(func.count()).select_from(statement.subquery())) or 0
    submissions = session.scalars(statement.order_by(
        Submission.created_at.desc(), Submission.ref).limit(
        limit).offset(offset)).all()
    items = [{
        'ref': submission.ref,
        'created_at': submission.created_at,
        'verification': 'ai_checked',
        'submitted_url': submission.submitted_url,
        'screening': screening_projection(
            _latest_run(session, submission)),
    } for submission in submissions]
    return items, total


def get_incoming(session: Session, ref: str) -> dict | None:
    submission = session.scalar(select(Submission).where(
        Submission.ref == ref, Submission.state == 'review_pending'))
    if submission is None:
        return None
    return {'ref': submission.ref, 'created_at': submission.created_at,
        'verification': 'ai_checked',
        'submitted_url': submission.submitted_url,
        'screening': screening_projection(
            _latest_run(session, submission))}

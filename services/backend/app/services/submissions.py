import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from os import environ
from pathlib import Path
from typing import BinaryIO, Protocol
from urllib.parse import urlsplit
from uuid import uuid4

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalogue import ModerationDecision
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

_HOST_LABEL = r'[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?'
_HOST_RE = re.compile(rf'{_HOST_LABEL}(\.{_HOST_LABEL})*')
_EMAIL_RE = re.compile(r'[^@\s]+@[^@\s]+\.[^@\s]+')

STATUS_LABELS = {
    'received': 'Diterima',
    'queued': 'Dalam antrean',
    'processing': 'Sedang diproses',
    'review_pending': 'Menunggu peninjauan moderator',
    'closed_unreviewed': 'Ditutup tanpa peninjauan',
}
DEFAULT_STATUS_LABEL = 'Ditutup'


class SubmissionError(Exception):
    """Domain rejection; the API layer maps it to HTTPException."""

    def __init__(self, status_code: int, detail: str):
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
    host = parts.hostname
    if not host or not _HOST_RE.fullmatch(host):
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
    uploads = [f for f in files if f.filename]
    if not submitted_url and not uploads:
        raise SubmissionError(422, 'Provide a url or at least one file')
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
        session.rollback()
        _cleanup(staged)
        raise
    return submission, receipt_token


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
    }

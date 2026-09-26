"""Data-retention sweeper.

Deletes expired uploads, redacts PII from purged submissions, closes stale
screening work, and removes orphaned staging files. Each unit commits on its
own so one bad row or file cannot wedge the sweep — failures roll back, bump
``errors``, and are logged without contents (storage keys / refs only).
"""
import logging
from datetime import datetime, timedelta, timezone
from os import environ

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.intake import ScreeningRun, Submission, Upload
from app.services.moderation import upload_file_path
from app.services.submissions import upload_root

STALE_HOURS_DEFAULT = 72
STAGING_MAX_AGE_HOURS_DEFAULT = 24

_ACTIVE_STATES = ('queued', 'processing')

logger = logging.getLogger(__name__)


def _as_utc(value: datetime | None) -> datetime | None:
    """Normalize for comparison — SQLite returns naive datetimes for
    DateTime(timezone=True) while Postgres returns aware ones; naive is UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _hours(override: int | None, env_name: str, default: int) -> int:
    if override is not None:
        return override
    return int(environ.get(env_name, default))


def _purged_result(result: dict) -> dict:
    """Copy ``result_json`` with purgeable text fields removed."""
    cleaned = dict(result)
    cleaned.pop('submission_text', None)
    evidence = cleaned.get('evidence')
    if isinstance(evidence, list):
        purged = []
        for item in evidence:
            if isinstance(item, dict):
                item = dict(item)
                item.pop('text', None)
                item['text_purged'] = True
            purged.append(item)
        cleaned['evidence'] = purged
    return cleaned


def _sweep_uploads(session: Session, now: datetime, counts: dict) -> None:
    uploads = session.scalars(select(Upload).where(
        Upload.delete_after.isnot(None))).all()
    for upload in uploads:
        if _as_utc(upload.delete_after) >= now:
            continue
        key = upload.storage_key
        try:
            path = upload_file_path(upload)
            # None means the key escaped the root or the file is already
            # gone — either way the retention record must still go.
            if path is not None:
                path.unlink(missing_ok=True)
            session.delete(upload)
            session.commit()
            counts['uploads_deleted'] += 1
        except Exception:
            session.rollback()
            counts['errors'] += 1
            logger.warning('failed to delete expired upload %s', key)


def _sweep_submissions(session: Session, now: datetime, counts: dict) -> None:
    submissions = session.scalars(select(Submission).where(
        Submission.purge_after.isnot(None))).all()
    for submission in submissions:
        if _as_utc(submission.purge_after) >= now:
            continue
        ref = submission.ref
        try:
            changed = False
            if submission.contact_email is not None:
                submission.contact_email = None
                changed = True
            runs = session.scalars(select(ScreeningRun).where(
                ScreeningRun.submission_id == submission.id)).all()
            for run in runs:
                result = run.result_json
                if not isinstance(result, dict):
                    continue
                cleaned = _purged_result(result)
                if cleaned != result:
                    # JSON columns only register changes on reassignment —
                    # in-place mutation would never reach the database.
                    run.result_json = cleaned
                    counts['runs_redacted'] += 1
                    changed = True
            if changed:
                counts['submissions_redacted'] += 1
            session.commit()
        except Exception:
            session.rollback()
            counts['errors'] += 1
            logger.warning('failed to redact submission %s', ref)


def _sweep_stale(session: Session, now: datetime, stale_hours: int,
        counts: dict) -> None:
    cutoff = now - timedelta(hours=stale_hours)
    submissions = session.scalars(select(Submission).where(
        Submission.state.in_(_ACTIVE_STATES))).all()
    for submission in submissions:
        updated = _as_utc(submission.updated_at)
        if updated is None or updated >= cutoff:
            continue
        ref = submission.ref
        try:
            submission.state = 'closed_unreviewed'
            submission.updated_at = now
            runs = session.scalars(select(ScreeningRun).where(
                ScreeningRun.submission_id == submission.id,
                ScreeningRun.state.in_(_ACTIVE_STATES))).all()
            for run in runs:
                run.state = 'failed'
                run.error = 'stale'
                run.finished_at = now
            session.commit()
            counts['stale_closed'] += 1
        except Exception:
            session.rollback()
            counts['errors'] += 1
            logger.warning('failed to close stale submission %s', ref)


def _sweep_staging(now: datetime, max_age_hours: int, counts: dict) -> None:
    staging = upload_root() / 'staging'
    if not staging.is_dir():
        return
    cutoff = (now - timedelta(hours=max_age_hours)).timestamp()
    try:
        entries = list(staging.iterdir())
    except OSError:
        counts['errors'] += 1
        logger.warning('could not list staging directory')
        return
    for path in entries:
        # Files only — never descend into or remove directories, and never
        # touch anything outside the staging directory itself.
        if not path.is_file():
            continue
        try:
            if path.stat().st_mtime >= cutoff:
                continue
            path.unlink()
            counts['staging_deleted'] += 1
        except Exception:
            counts['errors'] += 1
            logger.warning('failed to remove staging file %s', path.name)


def sweep_expired(session: Session, *, now: datetime | None = None,
        stale_hours: int | None = None,
        staging_max_age_hours: int | None = None) -> dict:
    now = _as_utc(now) or datetime.now(timezone.utc)
    stale_hours = _hours(stale_hours, 'STALE_HOURS', STALE_HOURS_DEFAULT)
    staging_max_age_hours = _hours(staging_max_age_hours,
        'STAGING_MAX_AGE_HOURS', STAGING_MAX_AGE_HOURS_DEFAULT)
    counts = {'uploads_deleted': 0, 'submissions_redacted': 0,
        'runs_redacted': 0, 'stale_closed': 0, 'staging_deleted': 0,
        'errors': 0}
    _sweep_uploads(session, now, counts)
    _sweep_submissions(session, now, counts)
    _sweep_stale(session, now, stale_hours, counts)
    _sweep_staging(now, staging_max_age_hours, counts)
    logger.info('retention sweep complete: %s', counts)
    return counts

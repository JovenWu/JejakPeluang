import logging
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.intake import JobOutbox

logger = logging.getLogger(__name__)


class Publisher(Protocol):
    """Event bus seam; a Celery/broker publisher replaces LoggingPublisher."""

    def publish(self, event_type: str, screening_run_id: UUID) -> None:
        ...


class LoggingPublisher:
    """Stub publisher: logs the event and counts as a successful delivery."""

    def __init__(self, log: logging.Logger | None = None):
        self._log = log or logger

    def publish(self, event_type: str, screening_run_id: UUID) -> None:
        self._log.info('outbox event %s for screening_run %s',
            event_type, screening_run_id)


def dispatch_pending(session: Session, publisher: Publisher) -> int:
    """Publish undelivered job_outbox rows; returns the delivered count.

    Each row is attempted once per call: ``attempts`` always increments,
    successes get ``delivered_at``, failures get ``last_error`` and are
    retried on the next call. Callers own the transaction (flush only here).
    """
    rows = session.scalars(select(JobOutbox).where(
        JobOutbox.delivered_at.is_(None)).order_by(
        JobOutbox.created_at)).all()
    delivered = 0
    for row in rows:
        row.attempts += 1
        try:
            publisher.publish(row.event_type, row.screening_run_id)
        except Exception as exc:
            row.last_error = str(exc)[:255]
        else:
            row.delivered_at = datetime.now(timezone.utc)
            delivered += 1
    session.flush()
    return delivered

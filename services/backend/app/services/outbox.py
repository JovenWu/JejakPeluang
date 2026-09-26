import logging
from datetime import datetime, timezone
from os import environ
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.intake import JobOutbox

logger = logging.getLogger(__name__)

QUEUE_KEY = 'jp:screening:queue'


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


class RedisPublisher:
    """Delivers screening-run ids to the worker via a Redis list."""

    def __init__(self, redis_url: str | None = None, client=None):
        if client is not None:
            self.client = client
        else:
            import redis as redis_lib
            if not redis_url:
                raise RuntimeError('RedisPublisher requires REDIS_URL')
            self.client = redis_lib.Redis.from_url(redis_url)

    def publish(self, event_type: str, screening_run_id: UUID) -> None:
        self.client.rpush(QUEUE_KEY, str(screening_run_id))


def make_publisher() -> Publisher:
    """Broker selection: Redis when configured, else the logging fallback."""
    redis_url = environ.get('REDIS_URL')
    if environ.get('JOB_BROKER') == 'redis' or redis_url:
        if not redis_url:
            raise RuntimeError('JOB_BROKER=redis requires REDIS_URL')
        return RedisPublisher(redis_url)
    return LoggingPublisher()


def default_publisher() -> Publisher:
    global _default
    try:
        return _default
    except NameError:
        _default = make_publisher()
        return _default


def pop_run_id(client, timeout_seconds: int = 5) -> UUID | None:
    """Blocking pop of one screening-run id from the worker queue.

    redis-py surfaces an empty BLPOP window as TimeoutError when a socket
    timeout is configured — that is a normal empty pop, not a failure.
    """
    import redis as redis_lib
    try:
        item = client.blpop(QUEUE_KEY, timeout=timeout_seconds)
    except redis_lib.exceptions.TimeoutError:
        return None
    if item is None:
        return None
    try:
        return UUID(item[1].decode())
    except (ValueError, AttributeError):
        return None


def push_run_id(client, run_id: UUID) -> None:
    client.rpush(QUEUE_KEY, str(run_id))


def dispatch_pending(session: Session,
        publisher: Publisher | None = None) -> int:
    """Publish undelivered job_outbox rows; returns the delivered count.

    Each row is attempted once per call: ``attempts`` always increments,
    successes get ``delivered_at``, failures get ``last_error`` and are
    retried on the next call. Callers own the transaction (flush only here).

    ``publisher`` defaults to :class:`LoggingPublisher`, an idempotent stub
    that counts as delivered; the Celery screening worker is expected to call
    this with a real broker publisher once the async pipeline lands. No HTTP
    endpoint exposes dispatch — it is invoked from worker/test code only.
    """
    publisher = publisher or LoggingPublisher()
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

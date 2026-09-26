"""Screening worker: consume outbox jobs and execute screening runs.

At-least-once delivery comes from the DB, not the broker: outbox rows stay
undelivered until published, queued/stale processing runs are re-enqueued by
the periodic sweep, and ``run_screening`` is idempotent by run id. Redis is
only a wake-up channel; without REDIS_URL the worker drains queued runs
directly (development mode).
"""
import logging
import time
from datetime import datetime, timedelta, timezone
from os import environ
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db import engine
from app.models.intake import ScreeningRun
from app.services.outbox import (RedisPublisher, dispatch_pending,
    make_publisher, pop_run_id, push_run_id)
from app.services.screening import (RUN_DEADLINE_SECONDS, default_clients,
    run_screening)

logger = logging.getLogger(__name__)

STALE_QUEUED_SECONDS = 60
STALE_PROCESSING_SECONDS = RUN_DEADLINE_SECONDS + 120
SWEEP_INTERVAL_SECONDS = 30
MAX_RUN_ATTEMPTS = 3


def process_run(session: Session, run: ScreeningRun, clients) -> None:
    """Run one screening idempotently; skips finished or exhausted runs.

    The conditional UPDATE is the claim: two workers racing the same run id
    get exactly one winner — the loser sees rowcount 0 and moves on. The claim
    commits immediately so the loser never waits on the winner's pipeline.
    """
    if (run.attempts or 0) >= MAX_RUN_ATTEMPTS:
        if run.state != 'failed':
            run.state = 'failed'
            run.error = 'max attempts exceeded'
            run.finished_at = datetime.now(timezone.utc)
            session.commit()
        return
    claimed = session.execute(update(ScreeningRun).where(
        ScreeningRun.id == run.id,
        ScreeningRun.state.in_(('queued', 'failed'))
    ).values(state='processing'),
        execution_options={'synchronize_session': False}).rowcount
    session.commit()
    if not claimed:
        return
    session.refresh(run)
    fetcher, searcher, llm, judge = clients
    try:
        run_screening(session, run, fetcher=fetcher, searcher=searcher,
            llm=llm, judge=judge)
    except Exception:
        logger.exception('screening run %s failed', run.id)


def _stale_runs(session: Session, now: datetime) -> list[ScreeningRun]:
    queued_cutoff = now - timedelta(seconds=STALE_QUEUED_SECONDS)
    processing_cutoff = now - timedelta(seconds=STALE_PROCESSING_SECONDS)
    return session.scalars(select(ScreeningRun).where(
        ((ScreeningRun.state == 'queued')
            & (ScreeningRun.created_at < queued_cutoff))
        | ((ScreeningRun.state == 'processing')
            & (ScreeningRun.started_at < processing_cutoff)))).all()


def sweep(session: Session, redis_client, publisher, clients) -> int:
    """Republish undelivered outbox rows and re-enqueue stale runs."""
    sent = dispatch_pending(session, publisher)
    session.commit()
    now = datetime.now(timezone.utc)
    requeued = 0
    for run in _stale_runs(session, now):
        if (run.attempts or 0) >= MAX_RUN_ATTEMPTS:
            if run.state != 'failed':
                run.state = 'failed'
                run.error = 'max attempts exceeded'
                run.finished_at = now
            continue
        if run.state == 'processing':
            # Atomically bounce a dead run back to 'queued' — a live worker
            # still holding it keeps the row because its state no longer
            # matches the WHERE clause mid-update.
            bounced = session.execute(update(ScreeningRun).where(
                ScreeningRun.id == run.id,
                ScreeningRun.state == 'processing',
                ScreeningRun.started_at
                < now - timedelta(seconds=STALE_PROCESSING_SECONDS)
            ).values(state='queued'),
                execution_options={'synchronize_session': False}).rowcount
            session.commit()
            if not bounced:
                continue
            session.refresh(run)
        if redis_client is not None:
            push_run_id(redis_client, run.id)
            requeued += 1
        else:
            process_run(session, run, clients)
    session.commit()
    if sent or requeued:
        logger.info('sweep: %d outbox published, %d runs requeued', sent,
            requeued)
    return sent + requeued


def main() -> None:
    logging.basicConfig(level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s %(message)s')
    for noisy in ('httpx', 'httpx2', 'typesafe_sdk'):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    from app.config import assert_production_config
    assert_production_config()
    clients = default_clients()
    publisher = make_publisher()
    redis_client = (publisher.client
        if isinstance(publisher, RedisPublisher) else None)
    if redis_client is not None:
        try:
            redis_client.ping()
        except Exception:
            logger.warning('redis unreachable at startup; sweeping only')
            redis_client = None
    logger.info('screening worker started (broker=%s)',
        'redis' if redis_client else 'db-poll')
    last_sweep = 0.0
    while True:
        run_id: UUID | None = None
        if redis_client is not None:
            try:
                run_id = pop_run_id(redis_client, timeout_seconds=5)
            except Exception:
                logger.exception('broker read failed; retrying')
                time.sleep(5)
        try:
            with Session(engine()) as session:
                if run_id is not None:
                    run = session.get(ScreeningRun, run_id)
                    if run is not None:
                        process_run(session, run, clients)
                if (time.monotonic() - last_sweep >= SWEEP_INTERVAL_SECONDS
                        or redis_client is None):
                    sweep(session, redis_client, publisher, clients)
                    last_sweep = time.monotonic()
        except Exception:
            # Startup races (schema not migrated yet) and transient DB
            # failures must not kill the worker — retry next cycle.
            logger.exception('worker cycle failed; retrying')
            time.sleep(5)
        if redis_client is None:
            time.sleep(5)


if __name__ == '__main__':
    main()

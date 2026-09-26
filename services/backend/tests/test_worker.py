from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.models.intake import JobOutbox, ScreeningRun, Submission
from app.services.outbox import (QUEUE_KEY, RedisPublisher, dispatch_pending,
    pop_run_id)
from app.services.screening import RUN_DEADLINE_SECONDS
from app.worker import MAX_RUN_ATTEMPTS, process_run, sweep

from test_screening import (FakeFetcher, FakeJudge, FakeLLM,
    FakeSearcher, make_submission, ok_page)

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


class FakeRedis:
    def __init__(self):
        self.items = []

    def rpush(self, key, value):
        self.items.append((key, value))
        return len(self.items)

    def blpop(self, key, timeout=0):
        for i, (k, v) in enumerate(self.items):
            if k == key:
                self.items.pop(i)
                return (key.encode(), str(v).encode())
        return None


def _clients(**overrides):
    return (overrides.get('fetcher', FakeFetcher({})),
        overrides.get('searcher', FakeSearcher()),
        overrides.get('llm', FakeLLM()),
        overrides.get('judge', FakeJudge()))


def test_redis_publisher_pushes_run_id():
    client = FakeRedis()
    publisher = RedisPublisher(client=client)
    run_id = uuid4()
    publisher.publish('screening.requested', run_id)
    assert client.items == [(QUEUE_KEY, str(run_id))]
    assert pop_run_id(client) == run_id
    assert pop_run_id(client) is None


def test_process_run_skips_completed_run(session):
    submission, run = make_submission(session)
    run.state = 'complete'
    session.commit()
    llm = FakeLLM()
    process_run(session, run, _clients(llm=llm))
    assert llm.extract_calls == 0
    assert run.attempts == 0


def test_process_run_executes_queued_run(session):
    submission, run = make_submission(session)
    fetcher = FakeFetcher({'https://peluang.example.org/info': ok_page()})
    process_run(session, run, _clients(fetcher=fetcher))
    assert run.state == 'complete'
    assert run.attempts == 1
    assert submission.state == 'review_pending'


def test_process_run_does_not_reclaim_processing_run(session):
    # Another worker holds this run — the claim UPDATE excludes 'processing',
    # so a second worker must not double-execute it.
    submission, run = make_submission(session)
    run.state = 'processing'
    run.started_at = datetime.now(timezone.utc)
    session.commit()
    llm = FakeLLM()
    process_run(session, run, _clients(llm=llm))
    assert llm.extract_calls == 0
    assert run.state == 'processing'
    assert run.attempts == 0


def test_process_run_marks_failed_after_max_attempts(session):
    submission, run = make_submission(session)
    run.attempts = MAX_RUN_ATTEMPTS
    session.commit()
    process_run(session, run, _clients())
    assert run.state == 'failed'
    assert run.error == 'max attempts exceeded'


def test_process_run_swallows_pipeline_error(session):
    submission, run = make_submission(session)
    fetcher = FakeFetcher({'https://peluang.example.org/info': ok_page()})
    llm = FakeLLM(compare_error=RuntimeError('poison'))
    process_run(session, run, _clients(fetcher=fetcher, llm=llm))
    assert run.state == 'failed'
    assert run.error == 'poison'


def test_sweep_reenqueues_stale_queued_run(session):
    submission, run = make_submission(session)
    run.created_at = datetime.now(timezone.utc) - timedelta(seconds=120)
    session.add(JobOutbox(event_type='screening.requested',
        screening_run_id=run.id, created_at=NOW,
        delivered_at=NOW, attempts=1))
    session.commit()
    client = FakeRedis()
    publisher = RedisPublisher(client=client)
    sweep(session, client, publisher, _clients())
    assert (QUEUE_KEY, str(run.id)) in client.items
    assert run.state == 'queued'  # untouched until the worker pops it


def test_sweep_publishes_undelivered_outbox_row(session):
    submission, run = make_submission(session)
    job = JobOutbox(event_type='screening.requested',
        screening_run_id=run.id, created_at=NOW)
    session.add(job)
    session.commit()
    client = FakeRedis()
    sweep(session, client, RedisPublisher(client=client), _clients())
    assert job.delivered_at is not None
    assert (QUEUE_KEY, str(run.id)) in client.items


def test_sweep_fails_stale_processing_run_at_max_attempts(session):
    submission, run = make_submission(session)
    run.state = 'processing'
    run.attempts = MAX_RUN_ATTEMPTS
    run.started_at = (datetime.now(timezone.utc)
        - timedelta(seconds=RUN_DEADLINE_SECONDS + 600))
    session.commit()
    client = FakeRedis()
    sweep(session, client, RedisPublisher(client=client), _clients())
    assert run.state == 'failed'
    assert client.items == []


def test_sweep_requeues_stale_processing_run(session):
    submission, run = make_submission(session)
    run.state = 'processing'
    run.attempts = 1
    run.started_at = (datetime.now(timezone.utc)
        - timedelta(seconds=RUN_DEADLINE_SECONDS + 600))
    session.commit()
    client = FakeRedis()
    sweep(session, client, RedisPublisher(client=client), _clients())
    session.refresh(run)
    assert run.state == 'queued'
    assert (QUEUE_KEY, str(run.id)) in client.items


def test_sweep_processes_inline_without_broker(session):
    submission, run = make_submission(session)
    run.created_at = datetime.now(timezone.utc) - timedelta(seconds=120)
    session.commit()
    fetcher = FakeFetcher({'https://peluang.example.org/info': ok_page()})
    from app.services.outbox import LoggingPublisher
    sweep(session, None, LoggingPublisher(), _clients(fetcher=fetcher))
    assert run.state == 'complete'


def test_duplicate_delivery_is_idempotent(session):
    submission, run = make_submission(session)
    fetcher = FakeFetcher({'https://peluang.example.org/info': ok_page()})
    clients = _clients(fetcher=fetcher)
    process_run(session, run, clients)
    process_run(session, run, clients)  # second delivery: no-op
    assert run.state == 'complete'
    assert run.attempts == 1

import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from app.models.intake import JobOutbox, ScreeningRun, Submission
from app.services.outbox import LoggingPublisher, dispatch_pending

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


def make_outbox_row(session, event_type='screening.requested'):
    submission = Submission(ref=f'JP-{uuid4().hex[:8].upper()}',
        receipt_token_hash='r' * 64,
        submitted_url='https://example.org/p', context='', state='queued',
        client_net_hash='n' * 64, created_at=NOW, updated_at=NOW)
    session.add(submission)
    session.flush()
    run = ScreeningRun(submission_id=submission.id, state='queued',
        created_at=NOW)
    session.add(run)
    session.flush()
    job = JobOutbox(event_type=event_type, screening_run_id=run.id,
        created_at=NOW)
    session.add(job)
    session.flush()
    return job


class RecordingPublisher:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def publish(self, event_type, screening_run_id):
        self.calls.append((event_type, screening_run_id))
        if self.fail:
            raise RuntimeError('broker down')


def test_dispatch_pending_marks_delivered(session):
    job = make_outbox_row(session)
    publisher = RecordingPublisher()
    delivered = dispatch_pending(session, publisher)
    session.commit()
    assert delivered == 1
    assert publisher.calls == [('screening.requested', job.screening_run_id)]
    assert job.delivered_at is not None
    assert job.attempts == 1
    assert job.last_error is None


def test_dispatch_pending_skips_delivered_rows(session):
    job = make_outbox_row(session)
    job.delivered_at = NOW
    session.flush()
    publisher = RecordingPublisher()
    assert dispatch_pending(session, publisher) == 0
    assert publisher.calls == []


def test_dispatch_pending_records_error_and_keeps_going(session):
    job = make_outbox_row(session)
    other = make_outbox_row(session)
    publisher = RecordingPublisher(fail=True)
    delivered = dispatch_pending(session, publisher)
    session.commit()
    assert delivered == 0
    for row in (job, other):
        assert row.delivered_at is None
        assert row.attempts == 1
        assert row.last_error == 'broker down'


def test_logging_publisher_logs_and_succeeds(session, caplog):
    job = make_outbox_row(session)
    with caplog.at_level(logging.INFO):
        delivered = dispatch_pending(session, LoggingPublisher())
    assert delivered == 1
    assert str(job.screening_run_id) in caplog.text
    assert 'screening.requested' in caplog.text
    row = session.scalar(select(JobOutbox).where(JobOutbox.id == job.id))
    assert row.delivered_at is not None

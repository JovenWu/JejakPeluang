import io
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models.intake import ScreeningRun, Submission, Upload
from app.services.fetch import FetchError
from app.services.providers import ProviderError, ProviderUnavailable
from app.services.screening import run_screening

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    target = tmp_path / 'uploads'
    monkeypatch.setenv('UPLOAD_DIR', str(target))
    return target


@dataclass
class FakeFetchResult:
    final_url: str
    status: int
    content_type: str
    content: bytes
    fetched_at: datetime = NOW


class FakeFetcher:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        outcome = self.mapping.get(url, FetchError('connect_failed', 'x'))
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeSearcher:
    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error
        self.calls = []

    def search(self, title, issuer, *, include_domains=None):
        self.calls.append({'title': title, 'issuer': issuer,
            'include_domains': include_domains})
        if self.error:
            raise self.error
        return self.results


class FakeLLM:
    def __init__(self, extraction=None, comparison=None,
            extract_error=None, compare_error=None):
        self.model = 'test-model'
        self.extraction = extraction or {
            'title': 'Beasiswa Unggulan 2026', 'issuer': 'Kemendikbud',
            'deadline': '2026-12-31', 'category': 'scholarship',
            'region': 'Indonesia', 'eligibility': 'S1 semester 4',
            'fees': None, 'requested_data': ['CV'],
            'source_hint': None}
        self.comparison = comparison or {
            'field_verdicts': {field: {'verdict': 'supported',
                'quote': 'q'} for field in
                ('title', 'issuer', 'deadline', 'category', 'region',
                    'eligibility')},
            'notes': None}
        self.extract_error = extract_error
        self.compare_error = compare_error
        self.extract_calls = 0
        self.compare_calls = 0

    def extract_fields(self, submission_text):
        self.extract_calls += 1
        if self.extract_error:
            raise self.extract_error
        return self.extraction

    def compare_fields(self, extraction, context, evidence):
        self.compare_calls += 1
        if self.compare_error:
            raise self.compare_error
        return self.comparison


class FakeJudge:
    def __init__(self, answers=None, error=None):
        self.answers = answers or {
            'doc_kind': {'type': 'choice', 'choice': 'official_listing',
                'probabilities': {'official_listing': 0.9}, 'confidence': 0.9},
            'official_announcement': {'type': 'noul', 'noul': 0.92},
            'content_match': {'type': 'noul', 'noul': 0.88},
            'deadline_ok': {'type': 'noul', 'noul': 0.8},
            'eligibility_ok': {'type': 'noul', 'noul': 0.75}}
        self.error = error
        self.calls = []

    def judge(self, state, *, has_deadline):
        self.calls.append({'state': state, 'has_deadline': has_deadline})
        if self.error:
            raise self.error
        return self.answers, 'jev-test-1.0'


def make_submission(session, *, url='https://peluang.example.org/info',
        context='', state='queued'):
    submission = Submission(ref='JP-TESTTEST', submitted_url=url,
        context=context, contact_email=None, state=state,
        client_net_hash='x' * 64, purge_after=NOW, created_at=NOW,
        updated_at=NOW, receipt_token_hash='y' * 64)
    session.add(submission)
    session.flush()
    run = ScreeningRun(submission_id=submission.id, state='queued',
        created_at=NOW)
    session.add(run)
    session.commit()
    return submission, run


def ok_page(url='https://peluang.example.org/info',
        text=b'Beasiswa Unggulan 2026 resmi Kemendikbud'):
    return FakeFetchResult(final_url=url, status=200,
        content_type='text/plain', content=text)


def test_orphaned_run_fails_cleanly(session):
    # A run whose submission row vanished must fail terminally — not crash on
    # a None dereference and wedge in 'processing' until the stale sweep.
    run = ScreeningRun(submission_id=uuid4(), state='queued', created_at=NOW)
    session.add(run)
    session.commit()

    result = run_screening(session, run, fetcher=FakeFetcher({}))

    assert result.state == 'failed'
    assert result.error == 'submission row missing'
    assert result.finished_at is not None


def test_run_url_submission_completes_end_to_end(session):
    submission, run = make_submission(session)
    fetcher = FakeFetcher({'https://peluang.example.org/info': ok_page()})
    searcher = FakeSearcher()
    llm, judge = FakeLLM(), FakeJudge()

    run_screening(session, run, fetcher=fetcher, searcher=searcher,
        llm=llm, judge=judge)

    assert run.state == 'complete'
    result = run.result_json
    assert result['outcome'] == 'complete'
    assert result['extraction']['title'] == 'Beasiswa Unggulan 2026'
    assert result['comparison']['field_verdicts']['title']['verdict'] == (
        'supported')
    assert result['judgments'][0]['answers'][
        'official_announcement']['noul'] == 0.92
    assert result['ai_source_match'] is True
    assert submission.state == 'review_pending'
    assert run.attempts == 1 and run.started_at is not None
    assert run.finished_at is not None
    assert 'test-model' in run.model_version
    assert 'jev-test-1.0' in run.model_version
    assert run.schema_version == '1'
    evidence = result['evidence']
    assert evidence[0]['origin'] == 'submitted_url'
    assert evidence[0]['final_url'] == 'https://peluang.example.org/info'


def test_run_discovers_candidates_via_tavily(session):
    submission, run = make_submission(session, url=None,
        context='Beasiswa Unggulan dari Kemendikbud')
    fetcher = FakeFetcher({'https://kemdikbud.go.id/beasiswa':
        ok_page('https://kemdikbud.go.id/beasiswa')})
    searcher = FakeSearcher(results=[
        {'url': 'https://kemdikbud.go.id/beasiswa', 'title': 'Resmi'},
        {'url': 'ftp://ignored.example/x', 'title': 'bad scheme'}])
    run_screening(session, run, fetcher=fetcher, searcher=searcher,
        llm=FakeLLM(), judge=FakeJudge())
    result = run.result_json
    assert result['outcome'] == 'complete'
    assert result['discovery']['status'] == 'ok'
    urls = [e['url'] for e in result['evidence']]
    assert urls == ['https://kemdikbud.go.id/beasiswa']


def test_run_extracts_uploaded_pdf(session, upload_dir):
    stream = (b'BT /F1 12 Tf 40 700 Td '
        b'(Beasiswa Unggulan 2026 resmi Kemendikbud) Tj ET')
    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R'
        b' /Resources << /Font << /F1 5 0 R >> >> >>',
        b'<< /Length ' + str(len(stream)).encode()
        + b' >>\nstream\n' + stream + b'\nendstream',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    buf = io.BytesIO()
    buf.write(b'%PDF-1.4\n')
    offsets = []
    for i, body in enumerate(objects, 1):
        offsets.append(buf.tell())
        buf.write(f'{i} 0 obj\n'.encode() + body + b'\nendobj\n')
    xref = buf.tell()
    buf.write(f'xref\n0 {len(objects) + 1}\n'.encode())
    buf.write(b'0000000000 65535 f \n')
    for off in offsets:
        buf.write(f'{off:010d} 00000 n \n'.encode())
    buf.write(b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'
        + str(xref).encode() + b'\n%%EOF')
    upload_dir.mkdir(parents=True)
    (upload_dir / 'aa11.pdf').write_bytes(buf.getvalue())

    submission, run = make_submission(session, url=None)
    session.add(Upload(submission_id=submission.id, storage_key='aa11.pdf',
        detected_mime='application/pdf', size_bytes=buf.tell(),
        page_count=1, sha256='z' * 64, delete_after=NOW))
    session.commit()

    run_screening(session, run, fetcher=FakeFetcher({}),
        searcher=FakeSearcher(), llm=FakeLLM(), judge=FakeJudge())
    assert 'Beasiswa Unggulan 2026' in run.result_json['submission_text']
    assert run.state == 'complete'


def test_fetch_failure_and_no_candidates_yields_no_public_source(session):
    submission, run = make_submission(session,
        context='Beasiswa Unggulan 2026 oleh Kemendikbud')
    fetcher = FakeFetcher({'https://peluang.example.org/info':
        FetchError('forbidden_host', 'private ip')})
    searcher = FakeSearcher(results=[])
    run_screening(session, run, fetcher=fetcher, searcher=searcher,
        llm=FakeLLM(), judge=FakeJudge())
    result = run.result_json
    assert result['outcome'] == 'no_public_source'
    assert result['evidence'][0]['fetch_error'] == 'forbidden_host'
    assert 'text' not in result['evidence'][0]
    assert result['ai_source_match'] is None
    assert run.state == 'complete'


def test_llm_unavailable_degrades_to_provider_unavailable(session):
    submission, run = make_submission(session)
    llm = FakeLLM(extract_error=ProviderUnavailable('rate limited'))
    run_screening(session, run, fetcher=FakeFetcher(
        {'https://peluang.example.org/info': ok_page()}),
        searcher=FakeSearcher(), llm=llm, judge=FakeJudge())
    assert run.result_json['outcome'] == 'provider_unavailable'
    assert run.result_json['errors'][0]['kind'] == 'provider_unavailable'
    assert run.state == 'complete'
    assert submission.state == 'review_pending'


def test_malformed_llm_output_marks_manual_review(session):
    submission, run = make_submission(session)
    llm = FakeLLM(extract_error=ProviderError('bad_response', 'not json'))
    run_screening(session, run, fetcher=FakeFetcher(
        {'https://peluang.example.org/info': ok_page()}),
        searcher=FakeSearcher(), llm=llm, judge=FakeJudge())
    assert run.result_json['outcome'] == 'manual_review_required'
    assert run.state == 'complete'


def test_no_content_outcome_when_nothing_extractable(session):
    submission, run = make_submission(session, url=None, context='')
    run_screening(session, run, fetcher=FakeFetcher({}),
        searcher=FakeSearcher(), llm=FakeLLM(), judge=FakeJudge())
    assert run.result_json['outcome'] == 'no_content'
    assert run.result_json['extraction'] is None
    assert run.state == 'complete'


def test_jev_failure_keeps_run_complete_without_judgments(session):
    submission, run = make_submission(session)
    judge = FakeJudge(error=ProviderUnavailable('jev down'))
    run_screening(session, run, fetcher=FakeFetcher(
        {'https://peluang.example.org/info': ok_page()}),
        searcher=FakeSearcher(), llm=FakeLLM(), judge=judge)
    result = run.result_json
    assert result['judgments'] is None
    assert result['ai_source_match'] is None
    assert any(e['stage'] == 'judge' for e in result['errors'])
    assert run.state == 'complete'


def test_conflicting_evidence_blocks_ai_source_match(session):
    submission, run = make_submission(session)
    comparison = {'field_verdicts': {field: {'verdict': 'supported',
            'quote': 'q'} for field in
            ('title', 'issuer', 'category', 'region', 'eligibility')} |
        {'deadline': {'verdict': 'conflicting', 'quote': 'lain'}},
        'notes': None}
    run_screening(session, run, fetcher=FakeFetcher(
        {'https://peluang.example.org/info': ok_page()}),
        searcher=FakeSearcher(), llm=FakeLLM(comparison=comparison),
        judge=FakeJudge())
    assert run.result_json['ai_source_match'] is False


def test_unexpected_error_marks_run_failed_and_raises(session):
    submission, run = make_submission(session)
    llm = FakeLLM(compare_error=RuntimeError('boom'))
    with pytest.raises(RuntimeError):
        run_screening(session, run, fetcher=FakeFetcher(
            {'https://peluang.example.org/info': ok_page()}),
            searcher=FakeSearcher(), llm=llm, judge=FakeJudge())
    assert run.state == 'failed'
    assert run.error == 'boom'
    assert submission.state == 'review_pending'


def test_terminal_submission_state_not_overwritten(session):
    submission, run = make_submission(session, state='rejected')
    run_screening(session, run, fetcher=FakeFetcher(
        {'https://peluang.example.org/info': ok_page()}),
        searcher=FakeSearcher(), llm=FakeLLM(), judge=FakeJudge())
    assert run.state == 'complete'
    assert submission.state == 'rejected'


def test_result_contains_no_scam_or_safe_verdict(session):
    submission, run = make_submission(session)
    run_screening(session, run, fetcher=FakeFetcher(
        {'https://peluang.example.org/info': ok_page()}),
        searcher=FakeSearcher(), llm=FakeLLM(), judge=FakeJudge())
    import json
    blob = json.dumps(run.result_json)
    for word in ('"scam"', '"safe"', 'penipuan', '"verdict": "safe"'):
        assert word not in blob.lower()


def test_known_issuer_domains_narrow_the_search(session, verified_issuer):
    submission, run = make_submission(session,
        url='https://example.org/beasiswa')
    fetcher = FakeFetcher({'https://example.org/beasiswa': ok_page(
        'https://example.org/beasiswa')})
    searcher = FakeSearcher(results=[])
    run_screening(session, run, fetcher=fetcher, searcher=searcher,
        llm=FakeLLM(), judge=FakeJudge())
    assert searcher.calls[0]['include_domains'] == ['example.org']


def test_tavily_error_marks_discovery_unavailable_but_completes(session):
    submission, run = make_submission(session, url=None,
        context='Beasiswa Unggulan')
    run_screening(session, run, fetcher=FakeFetcher({}),
        searcher=FakeSearcher(error=ProviderUnavailable('503')),
        llm=FakeLLM(), judge=FakeJudge())
    result = run.result_json
    assert result['discovery']['status'] == 'provider_unavailable'
    assert run.state == 'complete'

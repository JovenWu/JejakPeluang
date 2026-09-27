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
            'region': 'Indonesia', 'description': 'Beasiswa untuk mahasiswa.',
            'eligibility': 'S1 semester 4', 'fees': None,
            'requested_data': ['CV'], 'application_url': None,
            'source_hint': None}
        self.comparison = comparison or {
            'field_verdicts': {field: {'verdict': 'supported',
                'quote': 'q'} for field in
                ('title', 'issuer', 'deadline', 'category', 'region',
                    'description', 'eligibility', 'fees', 'requested_data')},
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
            'issuer_website': {'type': 'noul', 'noul': 0.92},
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
    assert run.schema_version == '2'
    evidence = result['evidence']
    assert evidence[0]['origin'] == 'submitted_url'
    assert evidence[0]['final_url'] == 'https://peluang.example.org/info'


def test_js_shell_page_marks_source_unreadable(session):
    # SPA mount pages (React/Vue shells) yield no readable text — the run
    # must flag them instead of feeding 'enable JavaScript' text to the LLM.
    shell = FakeFetchResult(final_url='https://peluang.example.org/info',
        status=200, content_type='text/html',
        content=(b'<!doctype html><html><body><noscript>You need to enable'
            b' JavaScript to run this app.</noscript>'
            b'<div id="root"></div></body></html>'))
    submission, run = make_submission(session)
    llm = FakeLLM()

    run_screening(session, run, fetcher=FakeFetcher(
        {'https://peluang.example.org/info': shell}), llm=llm,
        judge=FakeJudge())

    result = run.result_json
    item = result['evidence'][0]
    assert item['extract_error'] == 'js_required'
    assert item['text'] == ''
    assert result['submission_text'] in (None, '')
    assert llm.extract_calls == 0
    assert result['outcome'] == 'no_content'
    assert any(e['kind'] == 'js_required' for e in result['errors'])


def test_js_shell_public_projection_marks_source(session):
    from app.services.submissions import screening_projection
    shell = FakeFetchResult(final_url='https://peluang.example.org/info',
        status=200, content_type='text/html',
        content=b'<html><body><noscript>x</noscript>'
        b'<div id="root"></div></body></html>')
    _, run = make_submission(session)
    run_screening(session, run, fetcher=FakeFetcher(
        {'https://peluang.example.org/info': shell}), llm=FakeLLM())

    view = screening_projection(run)
    assert view['sources'][0]['error'] == 'js_required'
    # the noscript body must not leak anywhere in the public projection
    assert 'JavaScript' not in str(view)


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
    llm = FakeLLM()
    llm.extraction['issuer'] = 'Example University'
    run_screening(session, run, fetcher=fetcher, searcher=searcher,
        llm=llm, judge=FakeJudge())
    assert searcher.calls[0]['include_domains'] == ['example.org']


def test_discovery_searches_the_issuer_website_separately():
    from app.services.screening import _discover

    class Searcher:
        def __init__(self):
            self.calls = []

        def search(self, title, issuer, *, include_domains=None):
            self.calls.append((title, issuer, include_domains))
            if title == 'situs resmi':
                return [{'url': 'https://penerbit.example.org',
                    'title': 'Situs penerbit'}]
            return []

    searcher = Searcher()
    result = _discover(searcher, {'title': 'Beasiswa X', 'issuer': 'Penerbit X'},
        [], [])

    assert len(searcher.calls) == 2
    assert result['results'][0]['purpose'] == 'issuer_website'
    assert result['results'][0]['url'] == 'https://penerbit.example.org'


def test_tavily_error_marks_discovery_unavailable_but_completes(session):
    submission, run = make_submission(session, url=None,
        context='Beasiswa Unggulan')
    run_screening(session, run, fetcher=FakeFetcher({}),
        searcher=FakeSearcher(error=ProviderUnavailable('503')),
        llm=FakeLLM(), judge=FakeJudge())
    result = run.result_json
    assert result['discovery']['status'] == 'provider_unavailable'
    assert run.state == 'complete'


def test_qr_destination_is_fetched_and_used_for_the_catalogue_draft(
        session, upload_dir):
    import qrcode
    url = 'https://kemdikbud.go.id/pendaftaran'
    image = qrcode.make(url)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    upload_dir.mkdir(parents=True)
    storage_key = 'qr-poster.png'
    (upload_dir / storage_key).write_bytes(buffer.getvalue())
    submission, run = make_submission(session, url=None)
    session.add(Upload(submission_id=submission.id, storage_key=storage_key,
        detected_mime='image/png', size_bytes=buffer.tell(), page_count=None,
        sha256='z' * 64, delete_after=NOW))
    session.commit()
    fetcher = FakeFetcher({url: ok_page(url,
        b'Beasiswa Unggulan 2026. Pendaftaran sampai 30 November.')})

    run_screening(session, run, fetcher=fetcher,
        searcher=FakeSearcher(results=[]), llm=FakeLLM(), judge=FakeJudge())

    result = run.result_json
    assert url in fetcher.calls
    assert result['qr_codes'][0]['url'] == url
    assert result['evidence'][0]['origin'] == 'qr_code'
    assert result['extraction_origin'] == 'qr_destination'
    assert result['site_assessment']['status'] == 'issuer_website_found'
    assert result['confidence']['score'] == 92


def test_social_preview_image_qr_is_fetched_through_the_screening_fetcher(session):
    import qrcode

    social_url = 'https://instagram.com/p/announcement'
    image_url = 'https://cdn.instagram.example/poster.png'
    qr_url = 'https://penerbit.example.org/pendaftaran'
    image = qrcode.make(qr_url)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    social_page = FakeFetchResult(final_url=social_url, status=200,
        content_type='text/html', content=(
            b'<html><body><article><h1>Beasiswa Unggulan 2026</h1>'
            b'<p>Kemendikbud membuka pendaftaran beasiswa.</p></article>'
            b'<meta property="og:image" content="'
            + image_url.encode() + b'"></body></html>'))
    image_page = FakeFetchResult(final_url=image_url, status=200,
        content_type='image/png', content=buffer.getvalue())
    qr_page = ok_page(qr_url, b'Pendaftaran Beasiswa Unggulan Kemendikbud')
    fetcher = FakeFetcher({social_url: social_page, image_url: image_page,
        qr_url: qr_page})
    submission, run = make_submission(session, url=social_url)

    run_screening(session, run, fetcher=fetcher,
        searcher=FakeSearcher(results=[]), llm=FakeLLM(), judge=FakeJudge())

    result = run.result_json
    assert image_url in fetcher.calls
    assert qr_url in fetcher.calls
    assert result['qr_codes'][0]['image_url'] == image_url
    assert result['extraction_origin'] == 'submitted_material_and_qr'
    assert result['site_assessment']['status'] == 'issuer_website_found'

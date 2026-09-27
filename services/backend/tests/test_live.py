"""Live provider tests — real OpenRouter, Tavily, TypeSafe Jev, and the real
SSRF fetcher against publicly resolvable pages.

Run with:  JP_LIVE_TESTS=1 uv run pytest -m live -q
Requires the provider keys in the environment. Costs real (tiny) credits.
"""
import logging
from datetime import datetime, timezone
from os import environ

import pytest

from app.services.fetch import fetch
from app.services.screening import run_screening
from app.services.screening_jev import TypeSafeJudge
from app.services.screening_openrouter import OpenRouterClient
from app.services.screening_tavily import TavilySearcher

from test_screening import make_submission

LIVE = environ.get('JP_LIVE_TESTS') == '1'
HAVE_KEYS = all(environ.get(k) for k in (
    'OPENROUTER_API_KEY', 'TAVILY_API_KEY', 'TYPESAFE_API_KEY'))

pytestmark = [pytest.mark.live, pytest.mark.skipif(not (LIVE and HAVE_KEYS),
    reason='needs JP_LIVE_TESTS=1 and all three provider keys')]

logger = logging.getLogger('live')

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)

# Realistic Indonesian opportunity texts — mixed legit/suspicious so the
# accuracy suite can check the model separates signal from noise.
SCHOLARSHIP_TEXT = (
    'Beasiswa Unggulan Kemendikbudristek 2026 dibuka untuk mahasiswa S1 '
    'semester 3-6 di seluruh Indonesia. Pendaftaran gratis melalui laman '
    'resmi beasiswaunggulan.kemdikbud.go.id paling lambat 30 November 2026. '
    'Peserta wajib mengunggah CV, transkrip nilai, dan surat rekomendasi '
    'rektor. Tidak ada biaya pendaftaran.')

SUSPICIOUS_TEXT = (
    'BEASISWA FULL S1 LUAR NEGERI!!! DM admin sekarang di Telegram '
    '@beasiswakaget, cukup bayar biaya pendaftaran Rp150.000 ke rekening '
    'BCA 123456 a.n. Admin. Kuota terbatas, kirim foto KTP dan KK via WA '
    '08123456789. Deadline malam ini!!!')

INTERNSHIP_TEXT = (
    'Program Magang Bersertifikat Kampus Merdeka batch 7 membuka posisi '
    'data analyst di Jakarta untuk mahasiswa aktif minimal semester 5. '
    'Pendaftaran ditutup 15 Oktober 2026 di kampusmerdeka.kemdikbud.go.id. '
    'Siapkan CV dan portofolio.')


def _extraction_ok(extraction):
    required = {'title', 'issuer', 'deadline', 'category', 'region',
        'description', 'eligibility', 'fees', 'requested_data',
        'application_url', 'source_hint'}
    return isinstance(extraction, dict) and required <= extraction.keys()


def test_live_openrouter_extracts_scholarship_fields():
    out = OpenRouterClient().extract_fields(SCHOLARSHIP_TEXT)
    logger.info('extraction: %r', out)
    assert _extraction_ok(out)
    assert out['title'] and 'beasiswa' in out['title'].lower()
    issuer = (out['issuer'] or '').lower()
    assert 'kemdikbud' in issuer or 'kemendikbud' in issuer
    assert out['deadline'] in ('2026-11-30', '2026-11-30T00:00:00')
    assert out['category'] == 'scholarship'
    assert out['fees'] is None or 'gratis' in (out['fees'] or '').lower() \
        or 'tidak ada' in (out['fees'] or '').lower()
    assert any('cv' in item.lower() for item in out['requested_data'])


def test_live_openrouter_extracts_fee_and_data_red_flags():
    out = OpenRouterClient().extract_fields(SUSPICIOUS_TEXT)
    logger.info('extraction(suspicious): %r', out)
    assert _extraction_ok(out)
    fees = (out['fees'] or '').lower()
    assert '150' in fees or 'rp' in fees or 'bayar' in fees
    data = ' '.join(out['requested_data']).lower()
    assert 'ktp' in data or 'kk' in data


def test_live_tavily_finds_candidate_sources():
    results = TavilySearcher().search('Beasiswa Unggulan Kemendikbudristek',
        'Kemendikbud')
    logger.info('tavily: %r', results)
    assert isinstance(results, list)
    assert any(r['url'].startswith('https://') for r in results)


def test_live_typesafe_returns_typed_judgments():
    judge = TypeSafeJudge()
    state = {
        'submitted': {'title': 'Beasiswa Unggulan Kemendikbudristek 2026',
            'issuer': 'Kemendikbudristek', 'deadline': '2026-11-30',
            'eligibility': 'S1 semester 3-6'},
        'submitter_context': '',
        'evidence': [{'url': 'https://beasiswaunggulan.kemdikbud.go.id',
            'text': SCHOLARSHIP_TEXT}]}
    answers, model = judge.judge(state, has_deadline=True)
    logger.info('jev model=%s answers=%r', model, answers)
    assert model
    assert set(answers) >= {'doc_kind', 'official_announcement',
        'issuer_website', 'source_authority', 'deadline_corroborated'}
    assert 0.0 <= answers['official_announcement']['noul'] <= 1.0
    assert answers['doc_kind']['choice'] in ('official_listing',
        'aggregator_repost', 'social_post', 'unrelated',
        'insufficient_evidence')


def test_live_fetch_extracts_real_page():
    result = fetch('https://example.com/')
    from app.services.extract import to_text
    text = to_text(result.content, result.content_type)
    assert result.status == 200
    assert 'example' in text.lower()


def test_live_full_pipeline_on_real_submission(session):
    """End to end: context-only submission -> extract -> Tavily discover ->
    real fetch of a discovered page -> compare -> Jev -> persisted result."""
    submission, run = make_submission(session, url=None,
        context='Beasiswa Unggulan Kemendikbudristek 2026, '
            'pendaftaran di beasiswaunggulan.kemdikbud.go.id')
    fetcher, searcher, llm, judge = (fetch, TavilySearcher(),
        OpenRouterClient(), TypeSafeJudge())
    run_screening(session, run, fetcher=fetcher, searcher=searcher,
        llm=llm, judge=judge)
    result = run.result_json
    logger.info('pipeline outcome=%s discovery=%r errors=%r',
        result['outcome'], result['discovery'], result['errors'])
    assert run.state == 'complete'
    assert result['outcome'] in ('complete', 'no_public_source',
        'provider_unavailable')
    assert result['extraction'] is not None
    assert submission.state == 'review_pending'
    if result['outcome'] == 'complete':
        assert result['comparison'] is not None
        assert result['judgments'] is not None
        assert result['ai_source_match'] in (True, False)


def test_live_accuracy_suite(session, caplog):
    """Accuracy gate: extraction must hit ~all must-have assertions on a
    battery of realistic Indonesian texts. Reports per-case misses."""
    llm = OpenRouterClient()
    cases = [
        ('scholarship', SCHOLARSHIP_TEXT, [
            ('category', lambda v: v == 'scholarship'),
            ('deadline', lambda v: v and v.startswith('2026-11-30')),
            ('issuer', lambda v: v and ('kemdikbud' in v.lower()
                or 'kemendikbud' in v.lower())),
        ]),
        ('internship', INTERNSHIP_TEXT, [
            ('category', lambda v: v in ('internship', 'scholarship')),
            ('deadline', lambda v: v and v.startswith('2026-10-15')),
        ]),
        ('suspicious', SUSPICIOUS_TEXT, [
            ('fees', lambda v: v and ('150' in v or 'rp' in v.lower())),
            ('requested_data',
                lambda v: any('ktp' in i.lower() for i in v)),
        ]),
    ]
    failures = []
    for name, text, checks in cases:
        out = llm.extract_fields(text)
        for field, pred in checks:
            if not pred(out.get(field)):
                failures.append(f'{name}.{field}={out.get(field)!r}')
    if failures:
        logger.warning('accuracy misses: %s', failures)
    # Hard floor: at most one missed check across the suite.
    assert len(failures) <= 1, failures

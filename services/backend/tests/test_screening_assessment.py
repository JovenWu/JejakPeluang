from app.services.screening_assessment import (build_evidence_confidence,
    build_site_assessment)


def extraction():
    return {
        'title': 'Beasiswa X',
        'issuer': 'Penerbit X',
        'deadline': '2026-12-31',
        'category': 'scholarship',
        'region': 'Indonesia',
        'description': 'Program beasiswa.',
        'eligibility': 'Mahasiswa aktif.',
        'fees': 'Gratis',
        'requested_data': ['CV'],
    }


def comparison(verdict='supported'):
    return {'field_verdicts': {
        field: {'verdict': verdict, 'quote': 'kutipan'} for field in (
            'title', 'issuer', 'deadline', 'category', 'region',
            'description', 'eligibility', 'fees', 'requested_data')}}


def test_known_moderator_confirmed_domain_is_distinct_from_social_sources():
    result = {
        'discovery': {'status': 'ok'},
        'evidence': [
            {'url': 'https://example.org/peluang', 'status': 200},
            {'url': 'https://instagram.com/p/123', 'status': 200},
        ],
        'judgments': [],
        'qr_codes': [{'url': 'https://example.org/daftar'}],
    }

    assessment = build_site_assessment(result, ['example.org'])

    assert assessment['status'] == 'issuer_website_found'
    assert assessment['issuer_websites'][0]['basis'] == 'moderator_confirmed_domain'
    assert assessment['social_sources'][0]['platform'] == 'Instagram'
    assert assessment['qr_codes_found'] == 1


def test_social_only_requires_a_completed_search_and_limits_confidence():
    result = {
        'discovery': {'status': 'no_results'},
        'evidence': [{'url': 'https://instagram.com/p/123', 'status': 200}],
        'judgments': [{'url': 'https://instagram.com/p/123', 'answers': {
            'source_authority': {'score': 2, 'confidence': 0.9}}}],
    }
    assessment = build_site_assessment(result, [])
    confidence = build_evidence_confidence(extraction(), comparison(), assessment)

    assert assessment['status'] == 'social_only'
    assert assessment['social_sources'][0]['issuer_channel'] is True
    assert confidence['score'] <= 55
    assert confidence['label'] == 'limited'


def test_unsearched_social_link_is_inconclusive():
    result = {
        'discovery': {'status': 'skipped'},
        'evidence': [{'url': 'https://instagram.com/p/123', 'fetch_error': 'http_error'}],
        'judgments': [],
    }

    assert build_site_assessment(result, [])['status'] == 'inconclusive'


def test_ai_assessed_website_uses_its_source_confidence():
    result = {
        'discovery': {'status': 'ok'},
        'evidence': [{'url': 'https://penerbit.example.org/beasiswa',
            'final_url': 'https://penerbit.example.org/beasiswa', 'status': 200}],
        'judgments': [{'url': 'https://penerbit.example.org/beasiswa',
            'answers': {'issuer_website': {'noul': 0.72}}}],
    }
    assessment = build_site_assessment(result, [])
    confidence = build_evidence_confidence(extraction(), comparison(), assessment)

    assert assessment['status'] == 'issuer_website_found'
    assert confidence['score'] == 72
    assert confidence['label'] == 'moderate'


def test_unjudged_web_page_is_not_reported_as_a_third_party_source():
    result = {
        'discovery': {'status': 'ok'},
        'evidence': [{'url': 'https://unknown.example.org/program',
            'status': 200, 'text': 'Pendaftaran program'}],
        'judgments': [],
    }

    assessment = build_site_assessment(result, [])

    assert assessment['status'] == 'inconclusive'
    assert assessment['third_party_sources'] == []
    assert assessment['unclassified_sources'][0]['url'] == (
        'https://unknown.example.org/program')


def test_confidence_is_unavailable_without_field_comparisons():
    assessment = {'status': 'issuer_website_found', 'issuer_websites': []}

    confidence = build_evidence_confidence(extraction(), None, assessment)

    assert confidence['score'] is None
    assert confidence['label'] == 'insufficient'

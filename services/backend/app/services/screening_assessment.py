from urllib.parse import urlsplit

SOCIAL_PLATFORMS = {
    'instagram.com': 'Instagram',
    'facebook.com': 'Facebook',
    'fb.com': 'Facebook',
    'tiktok.com': 'TikTok',
    'x.com': 'X',
    'twitter.com': 'X',
    'youtube.com': 'YouTube',
    'youtu.be': 'YouTube',
    'linkedin.com': 'LinkedIn',
    'threads.net': 'Threads',
    't.me': 'Telegram',
    'telegram.me': 'Telegram',
    'wa.me': 'WhatsApp',
    'whatsapp.com': 'WhatsApp',
}


def _host(url: str | None) -> str | None:
    try:
        return (urlsplit(url).hostname or '').lower() or None
    except ValueError:
        return None


def _under_domain(host: str, domain: str) -> bool:
    domain = domain.lower().strip('.')
    return host == domain or host.endswith(f'.{domain}')


def _platform(host: str) -> str | None:
    for domain, label in SOCIAL_PLATFORMS.items():
        if _under_domain(host, domain):
            return label
    return None


def build_site_assessment(result: dict, known_domains: list[str]) -> dict:
    judgments = {}
    for page in result.get('judgments') or []:
        url = page.get('url')
        if url:
            judgments[url] = page.get('answers') or {}
    sites: list[dict] = []
    social: list[dict] = []
    other: list[dict] = []
    unclassified: list[dict] = []
    seen: set[str] = set()
    for item in result.get('evidence') or []:
        url = item.get('final_url') or item.get('url')
        if not isinstance(url, str) or not url:
            continue
        host = _host(url)
        if not host or url in seen:
            continue
        answers = judgments.get(url) or judgments.get(item.get('url')) or {}
        platform = _platform(host)
        if item.get('fetch_error') and not platform:
            continue
        known = any(_under_domain(host, domain) for domain in known_domains)
        if (not platform and not known and not item.get('text')
                and not answers):
            continue
        seen.add(url)
        authority = answers.get('source_authority') or {}
        authority_score = authority.get('score')
        if platform:
            social.append({
                'url': url,
                'platform': platform,
                'issuer_channel': isinstance(authority_score, (int, float))
                    and authority_score >= 2,
                'confidence': authority.get('confidence'),
            })
            continue
        issuer_site_score = (answers.get('issuer_website') or {}).get('noul')
        if known or (isinstance(issuer_site_score, (int, float))
                and issuer_site_score >= 0.65):
            sites.append({
                'url': url,
                'basis': 'moderator_confirmed_domain' if known else 'ai_assessed',
                'confidence': 1.0 if known else issuer_site_score,
            })
        elif (answers.get('doc_kind') or {}).get('choice') in (
                'aggregator_repost', 'aggregator') or authority_score == 1:
            other.append({'url': url})
        else:
            unclassified.append({'url': url})
    discovery_status = (result.get('discovery') or {}).get('status')
    if sites:
        status = 'issuer_website_found'
    elif unclassified:
        status = 'inconclusive'
    elif social and other:
        status = 'social_and_third_party'
    elif social and discovery_status == 'no_results':
        status = 'social_only'
    elif social:
        status = 'inconclusive'
    elif other:
        status = 'third_party_only'
    elif discovery_status == 'no_results':
        status = 'no_source_found'
    else:
        status = 'inconclusive'
    qr_urls = {item.get('url') for item in result.get('qr_codes') or []
        if isinstance(item, dict) and item.get('url')}
    return {
        'status': status,
        'issuer_websites': sites,
        'social_sources': social,
        'third_party_sources': other,
        'unclassified_sources': unclassified,
        'qr_codes_found': len(qr_urls),
    }


def build_evidence_confidence(extraction: dict | None, comparison: dict | None,
        site_assessment: dict) -> dict:
    verdicts = (comparison or {}).get('field_verdicts') or {}
    checked = [entry for entry in verdicts.values()
        if isinstance(entry, dict) and entry.get('verdict') in (
            'supported', 'conflicting', 'not_found', 'unreadable')]
    fields = ('title', 'issuer', 'deadline', 'category', 'region',
        'description', 'eligibility', 'fees', 'requested_data')
    available = [field for field in fields if (extraction or {}).get(field)]
    supported = sum(entry.get('verdict') == 'supported' for entry in checked)
    if not checked or not available:
        return {
            'score': None,
            'label': 'insufficient',
            'fields_available': len(available),
            'fields_checked': len(checked),
            'fields_supported': supported,
            'source_level': site_assessment.get('status', 'inconclusive'),
            'method': 'evidence-support-v1',
        }
    status = site_assessment.get('status')
    source_factor = {
        'third_party_only': 0.6,
        'social_and_third_party': 0.55,
        'social_only': 0.35,
        'no_source_found': 0.0,
        'inconclusive': 0.2,
    }.get(status, 0.2)
    if status == 'issuer_website_found':
        confidences = [site.get('confidence') for site in
            site_assessment.get('issuer_websites') or []]
        known = any(site.get('basis') == 'moderator_confirmed_domain'
            for site in site_assessment.get('issuer_websites') or [])
        source_factor = 1.0 if known else min(1.0, max(0.0, max(
            (value for value in confidences if isinstance(value, (int, float))),
            default=0.65)))
    elif status == 'social_only':
        confidences = [source.get('confidence') for source in
            site_assessment.get('social_sources') or []
            if source.get('issuer_channel')]
        if confidences:
            source_factor = min(0.55, max(confidences) * 0.55)
    agreement = supported / len(checked)
    coverage = min(1.0, len(checked) / len(available))
    score = round(100 * agreement * (0.75 + 0.25 * coverage) * source_factor)
    label = 'strong' if score >= 80 else 'moderate' if score >= 55 else 'limited'
    return {
        'score': score,
        'label': label,
        'fields_available': len(available),
        'fields_checked': len(checked),
        'fields_supported': supported,
        'source_level': site_assessment.get('status', 'inconclusive'),
        'method': 'evidence-support-v1',
    }

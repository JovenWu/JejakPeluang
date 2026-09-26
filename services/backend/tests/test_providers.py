import json
from uuid import uuid4

import httpx
import pytest

from app.services.providers import (ProviderError, ProviderUnavailable,
    post_json)
from app.services.screening_jev import TypeSafeJudge, answers_to_json
from app.services.screening_openrouter import OpenRouterClient
from app.services.screening_tavily import TavilySearcher


def responder(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_post_json_retries_on_429_then_succeeds():
    calls = []
    def handler(request):
        calls.append(request)
        if len(calls) < 3:
            return httpx.Response(429, headers={'retry-after': '0'})
        return httpx.Response(200, json={'ok': True})
    body = post_json('https://p.example/x', headers={}, payload={},
        client=responder(handler), sleeper=lambda s: None)
    assert body == {'ok': True}
    assert len(calls) == 3


def test_post_json_retries_on_5xx_and_timeout():
    def handler(request):
        if handler.n == 0:
            handler.n += 1
            raise httpx.ConnectTimeout('slow')
        handler.n += 1
        return httpx.Response(500)
    handler.n = 0
    with pytest.raises(ProviderUnavailable) as exc:
        post_json('https://p.example/x', headers={}, payload={},
            client=responder(handler), sleeper=lambda s: None,
            max_attempts=3)
    assert exc.value.kind == 'provider_unavailable'
    assert handler.n == 3


def test_post_json_4xx_fails_immediately():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(401, json={'error': 'bad key'})
    with pytest.raises(ProviderError) as exc:
        post_json('https://p.example/x', headers={}, payload={},
            client=responder(handler), sleeper=lambda s: None)
    assert exc.value.status == 401
    assert len(calls) == 1


def test_post_json_non_json_body_is_bad_response():
    def handler(request):
        return httpx.Response(200, text='<html>nope</html>')
    with pytest.raises(ProviderError) as exc:
        post_json('https://p.example/x', headers={}, payload={},
            client=responder(handler), sleeper=lambda s: None)
    assert exc.value.kind == 'bad_response'


def _chat_response(payload: dict):
    return httpx.Response(200, json={
        'id': 'x', 'model': 'test',
        'choices': [{'index': 0, 'message': {'role': 'assistant',
            'content': json.dumps(payload)}}]})


def test_openrouter_extract_parses_schema_content():
    seen = {}
    expected = {'title': 'Beasiswa X', 'issuer': 'Y', 'deadline': None,
        'category': 'scholarship', 'region': None, 'eligibility': None,
        'fees': None, 'requested_data': [], 'source_hint': None}
    def handler(request):
        seen['body'] = json.loads(request.content)
        seen['auth'] = request.headers.get('authorization')
        return _chat_response(expected)
    client = OpenRouterClient(api_key='k', client=responder(handler),
        sleeper=lambda s: None)
    assert client.extract_fields('teks') == expected
    assert seen['auth'] == 'Bearer k'
    assert seen['body']['temperature'] == 0
    assert seen['body']['response_format']['type'] == 'json_schema'


def test_openrouter_missing_choices_is_bad_response():
    def handler(request):
        return httpx.Response(200, json={'choices': []})
    client = OpenRouterClient(api_key='k', client=responder(handler))
    with pytest.raises(ProviderError) as exc:
        client.extract_fields('t')
    assert exc.value.kind == 'bad_response'


def test_openrouter_non_json_content_is_bad_response():
    def handler(request):
        return httpx.Response(200, json={
            'choices': [{'message': {'content': 'not json{'}}]})
    client = OpenRouterClient(api_key='k', client=responder(handler))
    with pytest.raises(ProviderError) as exc:
        client.extract_fields('t')
    assert exc.value.kind == 'bad_response'


def test_tavily_search_sends_minimized_query():
    seen = {}
    def handler(request):
        seen['body'] = json.loads(request.content)
        return httpx.Response(200, json={'results': [
            {'url': 'https://a.example/x', 'title': 'A', 'content': 'snip'},
            {'url': 'https://b.example/y'},
            'garbage-row']})
    searcher = TavilySearcher(api_key='k', client=responder(handler))
    results = searcher.search('Beasiswa Unggulan', 'Kemendikbud',
        include_domains=['kemdikbud.go.id'])
    assert seen['body']['query'] == 'Beasiswa Unggulan Kemendikbud'
    assert seen['body']['include_domains'] == ['kemdikbud.go.id']
    assert seen['body']['max_results'] == 5
    assert results == [{'url': 'https://a.example/x', 'title': 'A'},
        {'url': 'https://b.example/y', 'title': ''}]


def test_tavily_empty_terms_returns_no_results():
    searcher = TavilySearcher(api_key='k', client=responder(
        lambda r: httpx.Response(500)))
    assert searcher.search(None, None) == []


def test_missing_api_key_is_config_error():
    client = OpenRouterClient(api_key='', client=responder(
        lambda r: httpx.Response(500)))
    with pytest.raises(ProviderError) as exc:
        client.extract_fields('t')
    assert exc.value.kind == 'config'


def test_jev_answers_serialize_to_json():
    from typesafe_sdk import NoulAnswer
    class Resp:
        model = 'jev-test'
        answers = {'official': NoulAnswer(type='noul', noul=0.9)}
    out = answers_to_json(Resp())
    assert out == {'official': {'type': 'noul', 'noul': 0.9}}


def test_jev_judge_wraps_sdk_errors():
    class Boom:
        def system_one(self, **kwargs):
            raise TimeoutError('slow')
    judge = TypeSafeJudge(api_key='k', client=Boom())
    with pytest.raises(ProviderError):
        judge.judge({'submitted': {}}, has_deadline=False)


def test_jev_judge_missing_key_is_config_error():
    judge = TypeSafeJudge(api_key='')
    with pytest.raises(ProviderError) as exc:
        judge.judge({}, has_deadline=False)
    assert exc.value.kind == 'config'

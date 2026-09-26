from datetime import date


def test_list_excludes_drafts_and_expired(client, make_entry):
    approved = make_entry('approved-scholarship')
    make_entry('draft-scholarship', status='draft')
    make_entry('expired-scholarship', status='expired', deadline=date(2020, 1, 1))
    response = client.get('/api/v1/opportunities?category=scholarship')
    assert response.status_code == 200
    assert [item['slug'] for item in response.json()['items']] == [approved.slug]
    assert response.json()['total'] == 1
    assert response.json()['items'][0]['ai_source_match'] is False


def test_missing_detail_is_404(client):
    assert client.get('/api/v1/opportunities/not-found').status_code == 404


def test_expired_detail_remains_explainable(client, make_entry):
    make_entry('expired-notice', status='expired', deadline=date(2020, 1, 1))
    response = client.get('/api/v1/opportunities/expired-notice')
    assert response.status_code == 200
    assert response.json()['status'] == 'expired'
    assert response.json()['source_url'] == 'https://example.org/notice'

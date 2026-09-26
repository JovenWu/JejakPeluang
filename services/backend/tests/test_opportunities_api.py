from datetime import date
from app.models.catalogue import ModerationDecision


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


def test_list_excludes_unreviewed_entries(client, make_entry, session):
    item = make_entry('unreviewed-scholarship')
    decision = session.get(ModerationDecision, item.moderation_decision_id)
    decision.status = 'rejected'
    session.flush()
    response = client.get('/api/v1/opportunities')
    assert response.status_code == 200
    assert response.json() == {'items': [], 'total': 0}


def test_detail_is_404_after_decision_revoked(client, make_entry, session):
    item = make_entry('revoked-scholarship')
    decision = session.get(ModerationDecision, item.moderation_decision_id)
    decision.status = 'rejected'
    session.flush()
    assert client.get(f'/api/v1/opportunities/{item.slug}').status_code == 404

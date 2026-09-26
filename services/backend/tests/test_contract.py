import json
from pathlib import Path
import pytest
from app.main import app


def test_catalogue_paths_and_contract_exist() -> None:
    spec = app.openapi()
    assert '/api/v1/opportunities' in spec['paths']
    assert '/api/v1/opportunities/{slug}' in spec['paths']
    params = spec['paths']['/api/v1/opportunities']['get']['parameters']
    assert {param['name'] for param in params} == {'category', 'q', 'limit', 'offset'}
    assert 'OpportunitySummary' in spec['components']['schemas']
    assert 'OpportunityDetail' in spec['components']['schemas']


# TODO(task-5): drop the xfail once Task 5 regenerates openapi.json + generated.ts
@pytest.mark.xfail(strict=True,
    reason='openapi.json regeneration deferred to Task 5')
def test_checked_in_openapi_matches_app() -> None:
    path = Path(__file__).resolve().parents[3] / 'packages/contracts/openapi.json'
    assert json.loads(path.read_text(encoding='utf-8')) == app.openapi()

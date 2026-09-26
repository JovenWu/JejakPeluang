from fastapi import APIRouter, HTTPException, Query
from app.schemas.opportunity import Category, OpportunityDetail, OpportunityListResponse

router = APIRouter(prefix='/opportunities', tags=['opportunities'])


@router.get('', response_model=OpportunityListResponse)
def list_opportunities(
    category: Category | None = None,
    q: str | None = None,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
) -> OpportunityListResponse:
    return OpportunityListResponse(items=[], total=0)


@router.get('/{slug}', response_model=OpportunityDetail)
def get_opportunity(slug: str) -> OpportunityDetail:
    raise HTTPException(status_code=404, detail='Opportunity not found')

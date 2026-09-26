from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_session
from app.schemas.opportunity import Category, OpportunityDetail, OpportunityListResponse, OpportunitySummary
from app.services.catalogue import get_public, list_public

router = APIRouter(prefix='/opportunities', tags=['opportunities'])


def to_summary(session: Session, item) -> OpportunitySummary:
    return OpportunitySummary(slug=item.slug, title=item.title, category=item.category,
        issuer_name=item.issuer.name, deadline=item.deadline, checked_at=item.checked_at,
        verified_at=item.verified_at, trust_basis=item.trust_basis,
        status=item.status, source_url=item.source_url, ai_source_match=False)


@router.get('', response_model=OpportunityListResponse)
def list_opportunities(session: Session = Depends(get_session),
    category: Category | None = None, q: str | None = None,
    limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0)):
    items, total = list_public(session, category=category, q=q, limit=limit, offset=offset)
    return OpportunityListResponse(items=[to_summary(session, item) for item in items], total=total)


@router.get('/{slug}', response_model=OpportunityDetail)
def get_opportunity(slug: str, session: Session = Depends(get_session)):
    item = get_public(session, slug)
    if item is None:
        raise HTTPException(status_code=404, detail='Opportunity not found')
    return OpportunityDetail(**to_summary(session, item).model_dump(),
        description=item.description, eligibility=item.eligibility, region=item.region)

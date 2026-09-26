from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from app.db import get_session
from app.schemas.moderation import ReportCreated, ReportRequest
from app.schemas.opportunity import Category, OpportunityDetail, OpportunityListResponse, OpportunitySummary
from app.security import RateLimiter, client_net_hash, get_rate_limiter
from app.services.catalogue import get_public, list_public
from app.services.moderation import create_report

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


@router.post('/{slug}/reports', status_code=201, response_model=ReportCreated)
def report_opportunity(slug: str, body: ReportRequest, request: Request,
    session: Session = Depends(get_session),
    limiter: RateLimiter = Depends(get_rate_limiter)):
    """Public community report; flags the listing for moderator review only.

    Rate-limited per client network hash. Creating a report never touches the
    opportunity's status or trust fields.
    """
    net_hash = client_net_hash(request)
    if not limiter.check(f'reports:{net_hash}', limit=20,
            window_seconds=3600):
        raise HTTPException(status_code=429,
            detail='Too many reports; try again later')
    item = get_public(session, slug)
    if item is None:
        raise HTTPException(status_code=404, detail='Opportunity not found')
    report = create_report(session, opportunity=item,
        category=body.category, description=body.description)
    return ReportCreated(id=report.id)

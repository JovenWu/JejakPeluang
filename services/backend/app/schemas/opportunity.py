from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, HttpUrl

Category = Literal['scholarship', 'internship', 'competition']
TrustBasis = Literal['public_source', 'issuer_confirmed_private']
Verification = Literal['ai_checked', 'moderator_verified']


class OpportunitySummary(BaseModel):
    slug: str
    title: str
    category: Category
    issuer_name: str
    deadline: date | None
    checked_at: datetime
    verified_at: datetime
    trust_basis: TrustBasis
    # every listed opportunity required a human approval; the badge pairs
    # with 'ai_checked' feed items that have not yet been reviewed
    verification: Verification = 'moderator_verified'
    status: Literal['published', 'expired', 'needs_review']
    source_url: HttpUrl | None
    # null when no screening signal exists (unscreened or Jev unavailable)
    ai_source_match: bool | None = None


class OpportunityDetail(OpportunitySummary):
    description: str
    eligibility: str
    region: str | None


class OpportunityListResponse(BaseModel):
    items: list[OpportunitySummary]
    total: int

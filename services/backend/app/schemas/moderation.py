from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.opportunity import Category

DecisionKind = Literal['approved', 'needs_more_evidence', 'rejected', 'expire']
ReportCategory = Literal['scam_suspect', 'deadline_wrong', 'link_broken',
    'info_incorrect', 'other']


class DecisionFields(BaseModel):
    """Opportunity payload a moderator supplies when approving a submission."""

    title: str = Field(min_length=1, max_length=240)
    category: Category
    description: str = Field(min_length=1)
    eligibility: str = Field(min_length=1)
    region: str | None = Field(None, max_length=160)
    deadline: date | None = None
    slug: str | None = Field(None, max_length=160,
        pattern=r'^[a-z0-9]+(-[a-z0-9]+)*$')
    issuer_name: str | None = Field(None, min_length=1, max_length=160)


class DecisionRequest(BaseModel):
    decision: DecisionKind
    reason: str | None = Field(None, max_length=2000)
    fields: DecisionFields | None = None


class DecisionResult(BaseModel):
    id: UUID
    status: str
    submission_id: UUID
    submission_state: str
    opportunity_slug: str | None = None


class QueueItem(BaseModel):
    id: UUID
    ref: str
    state: str
    created_at: datetime
    submitted_url_host: str | None
    uploads_count: int
    has_contact_email: bool
    open_reports_count: int


class QueueResponse(BaseModel):
    items: list[QueueItem]
    total: int


class UploadMeta(BaseModel):
    id: UUID
    storage_key: str
    detected_mime: str
    size_bytes: int
    page_count: int | None


class ScreeningRunMeta(BaseModel):
    id: UUID
    state: str
    provider_version: str | None
    model_version: str | None
    schema_version: str | None
    created_at: datetime


class DecisionView(BaseModel):
    id: UUID
    status: str
    reason: str | None
    actor_id: UUID
    decided_at: datetime


class ReportView(BaseModel):
    id: UUID
    category: str
    description: str | None
    status: str
    created_at: datetime


class SubmissionDetail(BaseModel):
    """Everything a moderator sees; receipt_token_hash is never included."""

    id: UUID
    ref: str
    state: str
    submitted_url: str | None
    context: str
    contact_email: str | None
    client_net_hash: str
    purge_after: datetime | None
    created_at: datetime
    updated_at: datetime
    uploads: list[UploadMeta]
    screening_run: ScreeningRunMeta | None
    decisions: list[DecisionView]
    linked_opportunity_slug: str | None
    reports: list[ReportView]


class ReportRequest(BaseModel):
    category: ReportCategory
    description: str | None = Field(None, max_length=2000)


class ReportCreated(BaseModel):
    id: UUID

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class SubmissionCreated(BaseModel):
    ref: str
    receipt_token: str
    status: str
    status_url: str


class SourceCheck(BaseModel):
    """One fetched source page and whether Jev judged it the issuer's
    official listing. Body text is never exposed publicly."""
    url: str
    status: int | None
    official: bool | None


class ScreeningErrorView(BaseModel):
    stage: str | None
    kind: str | None


class ScreeningView(BaseModel):
    """Guest/public-safe projection of a screening run — extracted fields,
    per-field source verdicts, and the official-source signal. No
    submission_text, evidence bodies, or provider internals."""
    state: str
    outcome: str | None
    extracted: dict[str, Any] | None
    field_verdicts: dict[str, Any] | None
    sources: list[SourceCheck]
    ai_source_match: bool | None
    errors: list[ScreeningErrorView]
    finished_at: datetime | None


class SubmissionStatus(BaseModel):
    ref: str
    state: str
    status_label: str
    created_at: datetime
    decision: str | None = None
    needs_more_evidence: bool = False
    screening: ScreeningView | None = None


class IncomingItem(BaseModel):
    """Public feed row: an AI-checked submission awaiting moderation."""
    ref: str
    created_at: datetime
    verification: Literal['ai_checked']
    submitted_url: str | None
    screening: ScreeningView | None


class IncomingListResponse(BaseModel):
    items: list[IncomingItem]
    total: int

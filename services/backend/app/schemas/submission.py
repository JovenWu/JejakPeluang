from datetime import datetime
from pydantic import BaseModel


class SubmissionCreated(BaseModel):
    ref: str
    receipt_token: str
    status: str
    status_url: str


class SubmissionStatus(BaseModel):
    ref: str
    state: str
    status_label: str
    created_at: datetime
    decision: str | None = None
    needs_more_evidence: bool = False

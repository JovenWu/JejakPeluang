import hashlib
import hmac

from fastapi import (APIRouter, Depends, File, Form, Header, HTTPException,
    Request, UploadFile)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.intake import Submission
from app.schemas.submission import SubmissionCreated, SubmissionStatus
from app.security import RateLimiter, client_net_hash, get_rate_limiter
from app.services.submissions import (FileScanner, SubmissionError,
    get_scanner, intake_submission, status_view)

router = APIRouter(prefix='/submissions', tags=['submissions'])


@router.post('', status_code=202, response_model=SubmissionCreated)
def create_submission(request: Request,
    url: str | None = Form(None),
    context: str | None = Form(None),
    contact_email: str | None = Form(None),
    files: list[UploadFile] = File(default=[]),
    session: Session = Depends(get_session),
    limiter: RateLimiter = Depends(get_rate_limiter),
    scanner: FileScanner = Depends(get_scanner)):
    net_hash = client_net_hash(request)
    if not limiter.check(f'intake:{net_hash}', limit=10,
            window_seconds=3600):
        raise HTTPException(status_code=429,
            detail='Too many submissions; try again later')
    try:
        submission, receipt_token = intake_submission(session, url=url,
            context=context, contact_email=contact_email,
            files=files, client_net=net_hash, scanner=scanner)
    except SubmissionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    return SubmissionCreated(ref=submission.ref,
        receipt_token=receipt_token, status=submission.state,
        status_url=f'/api/v1/submissions/{submission.ref}')


@router.get('/{ref}', response_model=SubmissionStatus)
def get_submission_status(ref: str, request: Request,
    x_receipt_token: str = Header(),
    session: Session = Depends(get_session),
    limiter: RateLimiter = Depends(get_rate_limiter)):
    net_hash = client_net_hash(request)
    if not limiter.check(f'status:{net_hash}', limit=30,
            window_seconds=3600):
        raise HTTPException(status_code=429, detail='Too many requests')
    if not x_receipt_token:
        raise HTTPException(status_code=401,
            detail='X-Receipt-Token header required')
    submission = session.scalar(
        select(Submission).where(Submission.ref == ref))
    if submission is None:
        raise HTTPException(status_code=404, detail='Submission not found')
    digest = hashlib.sha256(x_receipt_token.encode()).hexdigest()
    if not hmac.compare_digest(digest, submission.receipt_token_hash):
        raise HTTPException(status_code=401, detail='Invalid receipt token')
    return status_view(session, submission)

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth import require_moderator
from app.db import get_session
from app.models.auth import User
from app.models.intake import Submission, Upload
from app.schemas.moderation import (DecisionRequest, DecisionResult,
    QueueResponse, SubmissionDetail)
from app.services.moderation import (ModerationError, decide, detail_view,
    list_queue, upload_file_path)

router = APIRouter(prefix='/moderation', tags=['moderation'])


def _get_submission_or_404(session: Session,
        submission_id: UUID) -> Submission:
    submission = session.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail='Submission not found')
    return submission


@router.get('/submissions', response_model=QueueResponse)
def list_submissions(state: str | None = None,
    limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    moderator: User = Depends(require_moderator)):
    items, total = list_queue(session, state=state, limit=limit,
        offset=offset)
    return QueueResponse(items=items, total=total)


@router.get('/submissions/{submission_id}', response_model=SubmissionDetail)
def get_submission_detail(submission_id: UUID,
    session: Session = Depends(get_session),
    moderator: User = Depends(require_moderator)):
    submission = _get_submission_or_404(session, submission_id)
    return SubmissionDetail(**detail_view(session, submission))


@router.get('/submissions/{submission_id}/uploads/{upload_id}')
def download_upload(submission_id: UUID, upload_id: UUID,
    session: Session = Depends(get_session),
    moderator: User = Depends(require_moderator)):
    """Stream a stored upload for moderator review.

    The upload row is looked up by id and must belong to the submission;
    upload_file_path resolves storage_key under UPLOAD_DIR and refuses any
    path outside it, so no user input ever reaches the filesystem.
    """
    submission = _get_submission_or_404(session, submission_id)
    upload = session.get(Upload, upload_id)
    if upload is None or upload.submission_id != submission.id:
        raise HTTPException(status_code=404, detail='Upload not found')
    path = upload_file_path(upload)
    if path is None:
        raise HTTPException(status_code=404, detail='Upload file not found')
    return FileResponse(path, media_type=upload.detected_mime,
        filename=upload.storage_key)


@router.post('/submissions/{submission_id}/decision',
    response_model=DecisionResult)
def post_decision(submission_id: UUID, body: DecisionRequest,
    session: Session = Depends(get_session),
    moderator: User = Depends(require_moderator)):
    submission = _get_submission_or_404(session, submission_id)
    try:
        decision, opportunity = decide(session, submission=submission,
            moderator=moderator, action=body.decision, reason=body.reason,
            fields=body.fields)
    except ModerationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    return DecisionResult(id=decision.id, status=decision.status,
        submission_id=submission.id, submission_state=submission.state,
        opportunity_slug=opportunity.slug if opportunity else None)

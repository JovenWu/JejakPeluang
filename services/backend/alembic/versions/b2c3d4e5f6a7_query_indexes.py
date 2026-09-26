"""query indexes for FK lookups and undelivered outbox rows

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index('ix_uploads_submission_id', 'uploads',
        ['submission_id'])
    op.create_index('ix_screening_runs_submission_id', 'screening_runs',
        ['submission_id'])
    op.create_index('ix_community_reports_opportunity_id',
        'community_reports', ['opportunity_id'])
    op.create_index('ix_job_outbox_pending', 'job_outbox', ['created_at'],
        postgresql_where=sa.text('delivered_at IS NULL'))


def downgrade() -> None:
    op.drop_index('ix_job_outbox_pending', table_name='job_outbox')
    op.drop_index('ix_community_reports_opportunity_id',
        table_name='community_reports')
    op.drop_index('ix_screening_runs_submission_id',
        table_name='screening_runs')
    op.drop_index('ix_uploads_submission_id', table_name='uploads')

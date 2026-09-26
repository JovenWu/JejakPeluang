"""screening results columns, private-tier source chain, approve-race index

Revision ID: a1b2c3d4e5f6
Revises: e32ba121f3f6
Create Date: 2026-09-26 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'e32ba121f3f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Screening runs carry the structured pipeline result for moderators.
    with op.batch_alter_table('screening_runs') as batch_op:
        batch_op.add_column(sa.Column('result_json', sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column('error', sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column('attempts', sa.Integer(), nullable=False,
                server_default='0'))
        batch_op.add_column(
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True))
    # issuer_confirmed_private listings have no public domain/evidence/url.
    with op.batch_alter_table('opportunities') as batch_op:
        batch_op.alter_column('issuer_domain_id', existing_type=sa.Uuid(),
            nullable=True)
        batch_op.alter_column('source_evidence_id', existing_type=sa.Uuid(),
            nullable=True)
        batch_op.alter_column('source_url',
            existing_type=sa.String(length=2048), nullable=True)
        batch_op.add_column(
            sa.Column('ai_source_match', sa.Boolean(), nullable=True))
    # Backstop for the double-approve race reviewers flagged: at most one
    # approved decision per submission, enforced at the database level.
    op.create_index('uq_moderation_decisions_one_approved',
        'moderation_decisions', ['submission_id'], unique=True,
        sqlite_where=sa.text("status = 'approved'"),
        postgresql_where=sa.text("status = 'approved'"))


def downgrade() -> None:
    op.drop_index('uq_moderation_decisions_one_approved',
        table_name='moderation_decisions')
    with op.batch_alter_table('opportunities') as batch_op:
        batch_op.drop_column('ai_source_match')
        batch_op.alter_column('source_url',
            existing_type=sa.String(length=2048), nullable=False)
        batch_op.alter_column('source_evidence_id', existing_type=sa.Uuid(),
            nullable=False)
        batch_op.alter_column('issuer_domain_id', existing_type=sa.Uuid(),
            nullable=False)
    with op.batch_alter_table('screening_runs') as batch_op:
        batch_op.drop_column('finished_at')
        batch_op.drop_column('error')
        batch_op.drop_column('result_json')

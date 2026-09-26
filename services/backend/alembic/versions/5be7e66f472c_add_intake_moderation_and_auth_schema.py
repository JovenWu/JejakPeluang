"""add intake moderation and auth schema

Revision ID: 5be7e66f472c
Revises: f751c5dcc7ff
Create Date: 2026-09-26 21:51:24.532445

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5be7e66f472c'
down_revision: Union[str, Sequence[str], None] = 'f751c5dcc7ff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('submissions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('ref', sa.String(length=16), nullable=False),
    sa.Column('receipt_token_hash', sa.String(length=64), nullable=False),
    sa.Column('submitted_url', sa.String(length=2048), nullable=True),
    sa.Column('context', sa.Text(), nullable=False),
    sa.Column('contact_email', sa.String(length=320), nullable=True),
    sa.Column('state', sa.String(length=32), nullable=False),
    sa.Column('client_net_hash', sa.String(length=64), nullable=False),
    sa.Column('purge_after', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('ref')
    )
    op.create_table('users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('hashed_password', sa.String(length=1024), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_superuser', sa.Boolean(), nullable=False),
    sa.Column('is_verified', sa.Boolean(), nullable=False),
    sa.Column('role', sa.String(length=32), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_table('access_tokens',
    sa.Column('token', sa.String(length=43), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('token')
    )
    op.create_index('ix_access_tokens_created_at', 'access_tokens', ['created_at'],
        unique=False)
    op.create_table('community_reports',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('opportunity_id', sa.Uuid(), nullable=False),
    sa.Column('category', sa.String(length=32), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('screening_runs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('submission_id', sa.Uuid(), nullable=False),
    sa.Column('state', sa.String(length=32), nullable=False),
    sa.Column('provider_version', sa.String(length=64), nullable=True),
    sa.Column('model_version', sa.String(length=64), nullable=True),
    sa.Column('schema_version', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('job_outbox',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('event_type', sa.String(length=64), nullable=False),
    sa.Column('screening_run_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('last_error', sa.String(length=255), nullable=True),
    sa.ForeignKeyConstraint(['screening_run_id'], ['screening_runs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('uploads',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('submission_id', sa.Uuid(), nullable=False),
    sa.Column('storage_key', sa.String(length=255), nullable=False),
    sa.Column('detected_mime', sa.String(length=64), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('page_count', sa.Integer(), nullable=True),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('delete_after', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('storage_key')
    )
    op.add_column('issuer_domains',
        sa.Column('verification_method', sa.String(length=64), nullable=True))
    with op.batch_alter_table('moderation_decisions') as batch_op:
        batch_op.add_column(sa.Column('submission_id', sa.Uuid(), nullable=True))
        batch_op.create_foreign_key('moderation_decisions_submission_id_fkey',
            'submissions', ['submission_id'], ['id'])
        batch_op.add_column(sa.Column('reason', sa.Text(), nullable=True))
    op.add_column('audit_events',
        sa.Column('entity_type', sa.String(length=32), server_default='opportunity',
            nullable=False))
    op.add_column('audit_events', sa.Column('entity_id', sa.Uuid(), nullable=True))


def downgrade() -> None:
    op.drop_column('audit_events', 'entity_id')
    op.drop_column('audit_events', 'entity_type')
    with op.batch_alter_table('moderation_decisions') as batch_op:
        batch_op.drop_column('reason')
        batch_op.drop_column('submission_id')
    op.drop_column('issuer_domains', 'verification_method')
    op.drop_table('uploads')
    op.drop_table('job_outbox')
    op.drop_table('screening_runs')
    op.drop_table('community_reports')
    op.drop_index('ix_access_tokens_created_at', table_name='access_tokens')
    op.drop_table('access_tokens')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
    op.drop_table('submissions')

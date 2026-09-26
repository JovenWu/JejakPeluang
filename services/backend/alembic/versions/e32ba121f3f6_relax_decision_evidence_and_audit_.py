"""relax decision evidence and audit nullability

Revision ID: e32ba121f3f6
Revises: 5be7e66f472c
Create Date: 2026-09-26 23:08:10.274198

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e32ba121f3f6'
down_revision: Union[str, Sequence[str], None] = '5be7e66f472c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Submission-scoped decisions need not carry source evidence (file-only
    # intakes have none); submission/opportunity audit rows likewise need a
    # nullable opportunity_id, and anonymous reporters have no actor id.
    with op.batch_alter_table('moderation_decisions') as batch_op:
        batch_op.alter_column('source_evidence_id', existing_type=sa.Uuid(),
            nullable=True)
    with op.batch_alter_table('audit_events') as batch_op:
        batch_op.alter_column('opportunity_id', existing_type=sa.Uuid(),
            nullable=True)
        batch_op.alter_column('actor_id', existing_type=sa.Uuid(),
            nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('audit_events') as batch_op:
        batch_op.alter_column('actor_id', existing_type=sa.Uuid(),
            nullable=False)
        batch_op.alter_column('opportunity_id', existing_type=sa.Uuid(),
            nullable=False)
    with op.batch_alter_table('moderation_decisions') as batch_op:
        batch_op.alter_column('source_evidence_id', existing_type=sa.Uuid(),
            nullable=False)

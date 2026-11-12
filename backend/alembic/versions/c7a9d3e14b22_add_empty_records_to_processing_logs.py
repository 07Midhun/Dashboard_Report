"""add empty_records to processing_logs

Revision ID: c7a9d3e14b22
Revises: b4e2f19a3c10
Create Date: 2026-11-11 10:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7a9d3e14b22'
down_revision: Union[str, Sequence[str], None] = 'b4e2f19a3c10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'processing_logs',
        sa.Column('empty_records', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('processing_logs', 'empty_records')


"""unique_constraint_category_monthly_snapshot

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3a4b5c6
Create Date: 2026-04-04

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        'uq_category_monthly_snapshot_category_month_year',
        'category_monthly_snapshots',
        ['category_id', 'month', 'year'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_category_monthly_snapshot_category_month_year',
        'category_monthly_snapshots',
        type_='unique',
    )

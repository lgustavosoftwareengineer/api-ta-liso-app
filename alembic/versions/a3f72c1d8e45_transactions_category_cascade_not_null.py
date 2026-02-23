"""transactions_category_cascade_not_null

Revision ID: a3f72c1d8e45
Revises: 6b1004e70010
Create Date: 2026-02-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3f72c1d8e45'
down_revision: Union[str, None] = '6b1004e70010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove orphaned transactions (category_id IS NULL) before enforcing NOT NULL
    op.execute("DELETE FROM transactions WHERE category_id IS NULL")

    # Drop the old FK (SET NULL) and recreate with CASCADE + NOT NULL
    op.drop_constraint('transactions_category_id_fkey', 'transactions', type_='foreignkey')
    op.alter_column('transactions', 'category_id', nullable=False)
    op.create_foreign_key(
        'transactions_category_id_fkey',
        'transactions', 'categories',
        ['category_id'], ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint('transactions_category_id_fkey', 'transactions', type_='foreignkey')
    op.alter_column('transactions', 'category_id', nullable=True)
    op.create_foreign_key(
        'transactions_category_id_fkey',
        'transactions', 'categories',
        ['category_id'], ['id'],
        ondelete='SET NULL',
    )

"""add_balance_fields_to_chat_messages

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("balance_available", sa.Numeric(12, 2), nullable=True))
    op.add_column("chat_messages", sa.Column("balance_requested", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_messages", "balance_requested")
    op.drop_column("chat_messages", "balance_available")

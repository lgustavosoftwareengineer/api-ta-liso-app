"""add_telegram_users_and_pending_auth

Revision ID: d1e2f3a4b5c6
Revises: b2c3d4e5f6a7
Create Date: 2026-03-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telegram_users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_telegram_users_telegram_chat_id", "telegram_users", ["telegram_chat_id"], unique=True)
    op.create_index("ix_telegram_users_user_id", "telegram_users", ["user_id"])

    op.create_table(
        "telegram_pending_auth",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_telegram_pending_auth_telegram_chat_id", "telegram_pending_auth", ["telegram_chat_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_telegram_pending_auth_telegram_chat_id", table_name="telegram_pending_auth")
    op.drop_table("telegram_pending_auth")
    op.drop_index("ix_telegram_users_user_id", table_name="telegram_users")
    op.drop_index("ix_telegram_users_telegram_chat_id", table_name="telegram_users")
    op.drop_table("telegram_users")

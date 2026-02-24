"""add_category_id_to_chat_messages

Revision ID: c8f4a2b3d05e
Revises: b7e3f91a2c04
Create Date: 2026-02-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8f4a2b3d05e"
down_revision: Union[str, None] = "b7e3f91a2c04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("category_id", sa.String(), nullable=True),
    )
    op.create_foreign_key(
        "fk_chat_messages_category_id",
        "chat_messages",
        "categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_chat_messages_category_id",
        "chat_messages",
        type_="foreignkey",
    )
    op.drop_column("chat_messages", "category_id")

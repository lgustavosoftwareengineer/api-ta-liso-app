"""default block_negative_balance true

Revision ID: a1b2c3d4e5f6
Revises: c8f4a2b3d05e
Create Date: 2026-02-24

"""
from typing import Sequence, Union

from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "c8f4a2b3d05e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE user_settings SET block_negative_balance = true WHERE block_negative_balance = false"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE user_settings SET block_negative_balance = false WHERE block_negative_balance = true"
    )

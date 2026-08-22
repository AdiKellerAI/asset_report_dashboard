"""add is_operating to expense_type

Revision ID: a6f966c5a581
Revises: f1f0c6d4ba04
Create Date: 2026-08-22 21:55:57.456254

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6f966c5a581'
down_revision: Union[str, Sequence[str], None] = 'f1f0c6d4ba04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default backfills every pre-existing expense_type row to True (an
    # existing category is operating unless explicitly seeded otherwise - see
    # app/seed.py) before the column is fixed NOT NULL.
    op.add_column(
        "expense_type",
        sa.Column("is_operating", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("expense_type", "is_operating", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("expense_type", "is_operating")

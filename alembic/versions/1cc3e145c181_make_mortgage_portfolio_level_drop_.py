"""make mortgage portfolio-level, drop property_id

Revision ID: 1cc3e145c181
Revises: a6f966c5a581
Create Date: 2026-08-23 21:21:35.766847

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1cc3e145c181'
down_revision: Union[str, Sequence[str], None] = 'a6f966c5a581'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(op.f('mortgage_property_id_fkey'), 'mortgage', type_='foreignkey')
    op.drop_column('mortgage', 'property_id')


def downgrade() -> None:
    """Downgrade schema.

    Nullable, not NOT NULL - there's no unambiguous property to attach any
    already-portfolio-level rows back to.
    """
    op.add_column('mortgage', sa.Column('property_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.create_foreign_key(op.f('mortgage_property_id_fkey'), 'mortgage', 'property', ['property_id'], ['id'])

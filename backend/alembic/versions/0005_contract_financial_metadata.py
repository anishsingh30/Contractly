"""Phase 14 Contract Financial Metadata and Committed Value Normalization

Revision ID: 0005_contract_financial_metadata
Revises: 0004_lawyer_admin_directory
Create Date: 2026-10-16 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0005_contract_financial_metadata'
down_revision: Union[str, None] = '0004_lawyer_admin_directory'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add auditable monetary metadata columns to contracts table
    op.add_column('contracts', sa.Column('value_basis', sa.String(length=50), nullable=True, server_default='NOT_SPECIFIED'))
    op.add_column('contracts', sa.Column('calculation_explanation', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('contracts', 'calculation_explanation')
    op.drop_column('contracts', 'value_basis')

"""Phase 13.3 Lawyer Admin Management and Public Directory Migration

Revision ID: 0004_lawyer_admin_directory
Revises: 0003_lawyer_matter_workflows
Create Date: 2026-10-14 23:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0004_lawyer_admin_directory'
down_revision: Union[str, None] = '0003_lawyer_matter_workflows'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add public professional and lifecycle fields
    op.add_column('lawyer_profiles', sa.Column('is_published', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('lawyer_profiles', sa.Column('professional_title', sa.String(length=100), nullable=True))
    op.add_column('lawyer_profiles', sa.Column('qualifications', sa.JSON(), nullable=True))
    op.add_column('lawyer_profiles', sa.Column('languages', sa.JSON(), nullable=True))
    op.add_column('lawyer_profiles', sa.Column('consultation_duration_minutes', sa.Integer(), nullable=False, server_default='30'))

    # Add private administrative fields
    op.add_column('lawyer_profiles', sa.Column('phone_number', sa.String(length=50), nullable=True))
    op.add_column('lawyer_profiles', sa.Column('internal_notes', sa.Text(), nullable=True))
    op.add_column('lawyer_profiles', sa.Column('credential_documents', sa.JSON(), nullable=True))

    op.create_index('ix_lawyer_profiles_is_published', 'lawyer_profiles', ['is_published'])


def downgrade() -> None:
    op.drop_index('ix_lawyer_profiles_is_published', 'lawyer_profiles')
    op.drop_column('lawyer_profiles', 'credential_documents')
    op.drop_column('lawyer_profiles', 'internal_notes')
    op.drop_column('lawyer_profiles', 'phone_number')
    op.drop_column('lawyer_profiles', 'consultation_duration_minutes')
    op.drop_column('lawyer_profiles', 'languages')
    op.drop_column('lawyer_profiles', 'qualifications')
    op.drop_column('lawyer_profiles', 'professional_title')
    op.drop_column('lawyer_profiles', 'is_published')

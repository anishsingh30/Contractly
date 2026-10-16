"""Phase 13.2 Lawyer Experience and Matter Workflows database migration

Revision ID: 0003_lawyer_matter_workflows
Revises: 0002_email_security_workflows
Create Date: 2026-10-14 11:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0003_lawyer_matter_workflows'
down_revision: Union[str, None] = '0002_email_security_workflows'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Lawyer Profiles
    op.create_table(
        'lawyer_profiles',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('organization_id', sa.String(length=36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('bar_council_number', sa.String(length=100), nullable=False),
        sa.Column('state_bar_council', sa.String(length=100), nullable=False),
        sa.Column('admitted_jurisdictions', sa.String(length=500), nullable=False),
        sa.Column('practice_areas', sa.JSON(), nullable=False),
        sa.Column('experience_years', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('consultation_fee', sa.String(length=100), nullable=False, server_default=''),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('is_available_for_inquiries', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('verification_status', sa.String(length=30), nullable=False, server_default='PENDING_REVIEW'),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('verified_by_user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_lawyer_profiles_user_id', 'lawyer_profiles', ['user_id'], unique=True)
    op.create_index('ix_lawyer_profiles_organization_id', 'lawyer_profiles', ['organization_id'])
    op.create_index('ix_lawyer_profiles_bar_council_number', 'lawyer_profiles', ['bar_council_number'], unique=True)
    op.create_index('ix_lawyer_profiles_verification_status', 'lawyer_profiles', ['verification_status'])

    # 2. Legal Matters
    op.create_table(
        'legal_matters',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('matter_code', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('matter_type', sa.String(length=100), nullable=False),
        sa.Column('client_organization_id', sa.String(length=36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('client_user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('lawyer_organization_id', sa.String(length=36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lawyer_user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('contract_id', sa.String(length=36), sa.ForeignKey('contracts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='SUBMITTED'),
        sa.Column('counterparty_name', sa.String(length=255), nullable=False),
        sa.Column('conflict_cleared', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('conflict_cleared_at', sa.DateTime(), nullable=True),
        sa.Column('conflict_cleared_by_user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('conflict_notes', sa.Text(), nullable=True),
        sa.Column('client_consent_given', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('client_consent_at', sa.DateTime(), nullable=True),
        sa.Column('client_consent_by_user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('preferred_time_slot', sa.String(length=100), nullable=True),
        sa.Column('client_notes', sa.Text(), nullable=True),
        sa.Column('scoping_notes', sa.Text(), nullable=True),
        sa.Column('decline_reason', sa.String(length=50), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_legal_matters_matter_code', 'legal_matters', ['matter_code'], unique=True)
    op.create_index('ix_legal_matters_client_organization_id', 'legal_matters', ['client_organization_id'])
    op.create_index('ix_legal_matters_client_user_id', 'legal_matters', ['client_user_id'])
    op.create_index('ix_legal_matters_lawyer_organization_id', 'legal_matters', ['lawyer_organization_id'])
    op.create_index('ix_legal_matters_lawyer_user_id', 'legal_matters', ['lawyer_user_id'])
    op.create_index('ix_legal_matters_contract_id', 'legal_matters', ['contract_id'])
    op.create_index('ix_legal_matters_status', 'legal_matters', ['status'])

    # 3. Matter Access Grants
    op.create_table(
        'matter_access_grants',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('matter_id', sa.String(length=36), sa.ForeignKey('legal_matters.id', ondelete='CASCADE'), nullable=False),
        sa.Column('contract_id', sa.String(length=36), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lawyer_user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('permission_level', sa.String(length=50), nullable=False, server_default='READ_ONLY'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('granted_at', sa.DateTime(), nullable=False),
        sa.Column('granted_by_user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_by_user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('revocation_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('matter_id', 'contract_id', 'lawyer_user_id', name='uq_matter_contract_lawyer_grant')
    )
    op.create_index('ix_matter_access_grants_matter_id', 'matter_access_grants', ['matter_id'])
    op.create_index('ix_matter_access_grants_contract_id', 'matter_access_grants', ['contract_id'])
    op.create_index('ix_matter_access_grants_lawyer_user_id', 'matter_access_grants', ['lawyer_user_id'])
    op.create_index('ix_matter_access_grants_is_active', 'matter_access_grants', ['is_active'])

    # 4. Matter Messages
    op.create_table(
        'matter_messages',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('matter_id', sa.String(length=36), sa.ForeignKey('legal_matters.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sender_user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sender_type', sa.String(length=20), nullable=False),
        sa.Column('message_text', sa.Text(), nullable=False),
        sa.Column('is_internal_note', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('attachments_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_matter_messages_matter_id', 'matter_messages', ['matter_id'])
    op.create_index('ix_matter_messages_sender_user_id', 'matter_messages', ['sender_user_id'])
    op.create_index('ix_matter_messages_is_internal_note', 'matter_messages', ['is_internal_note'])

    # 5. Lawyer Availability
    op.create_table(
        'lawyer_availability',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('lawyer_profile_id', sa.String(length=36), sa.ForeignKey('lawyer_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.String(length=10), nullable=False),
        sa.Column('end_time', sa.String(length=10), nullable=False),
        sa.Column('slot_duration_minutes', sa.Integer(), nullable=False, server_default='45'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_lawyer_availability_lawyer_profile_id', 'lawyer_availability', ['lawyer_profile_id'])
    op.create_index('ix_lawyer_avail_profile_day', 'lawyer_availability', ['lawyer_profile_id', 'day_of_week'])


def downgrade() -> None:
    op.drop_table('lawyer_availability')
    op.drop_table('matter_messages')
    op.drop_table('matter_access_grants')
    op.drop_table('legal_matters')
    op.drop_table('lawyer_profiles')

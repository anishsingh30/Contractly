"""Phase 5 Email Delivery and Account Security Workflows schema migration

Revision ID: 0002_email_security_workflows
Revises: 0001_initial_schema
Create Date: 2026-10-13 17:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0002_email_security_workflows'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Account Tokens (Email verification, Password reset)
    op.create_table(
        'account_tokens',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('token_type', sa.String(length=30), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_used', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_account_tokens_user_id', 'account_tokens', ['user_id'])
    op.create_index('ix_account_tokens_token_hash', 'account_tokens', ['token_hash'])
    op.create_index('ix_account_tokens_token_type', 'account_tokens', ['token_type'])

    # 2. Organization Invitations
    op.create_table(
        'organization_invitations',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('inviter_user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('invitee_email', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='MEMBER'),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='PENDING'),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_organization_invitations_organization_id', 'organization_invitations', ['organization_id'])
    op.create_index('ix_organization_invitations_invitee_email', 'organization_invitations', ['invitee_email'])
    op.create_index('ix_organization_invitations_token_hash', 'organization_invitations', ['token_hash'])


def downgrade() -> None:
    op.drop_table('organization_invitations')
    op.drop_table('account_tokens')

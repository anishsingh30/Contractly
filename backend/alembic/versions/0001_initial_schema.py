"""Initial schema baseline for Contractly

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-13 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Organizations
    op.create_table(
        'organizations',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('account_type', sa.String(length=30), nullable=False, server_default='BUSINESS'),
        sa.Column('subscription_tier', sa.String(length=50), server_default='ENTERPRISE'),
        sa.Column('storage_quota_bytes', sa.BigInteger(), server_default='10737418240'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_organizations_slug', 'organizations', ['slug'], unique=True)

    # 2. Departments
    op.create_table(
        'departments',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('budget_currency', sa.String(length=3), server_default='INR'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_departments_organization_id', 'departments', ['organization_id'])

    # 3. Users
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='1'),
        sa.Column('is_super_admin', sa.Boolean(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # 4. Organization Members
    op.create_table(
        'organization_members',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('department_id', sa.String(length=36), nullable=True),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='LEGAL_MANAGER'),
        sa.Column('status', sa.String(length=30), server_default='ACTIVE'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_organization_members_organization_id', 'organization_members', ['organization_id'])
    op.create_index('ix_organization_members_user_id', 'organization_members', ['user_id'])

    # 5. Contracts
    op.create_table(
        'contracts',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('contract_id', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('contract_type', sa.String(length=100), nullable=False),
        sa.Column('counterparty', sa.String(length=255), nullable=False),
        sa.Column('department', sa.String(length=100), server_default='Legal'),
        sa.Column('owner', sa.String(length=255), server_default='Legal Manager'),
        sa.Column('value', sa.Numeric(precision=15, scale=2), server_default='0.0'),
        sa.Column('currency', sa.String(length=3), server_default='INR'),
        sa.Column('start_date', sa.String(length=20), nullable=True),
        sa.Column('expiry_date', sa.String(length=20), nullable=True),
        sa.Column('renewal_date', sa.String(length=20), nullable=True),
        sa.Column('auto_renew', sa.Boolean(), server_default='0'),
        sa.Column('renewal_notice_days', sa.Integer(), server_default='30'),
        sa.Column('termination_notice_days', sa.Integer(), server_default='30'),
        sa.Column('termination_date', sa.String(length=20), nullable=True),
        sa.Column('termination_reason', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='UNDER_REVIEW'),
        sa.Column('composite_risk_score', sa.Integer(), server_default='0'),
        sa.Column('risk_level', sa.String(length=20), server_default='LOW'),
        sa.Column('version', sa.String(length=20), server_default='v1.0'),
        sa.Column('governing_law', sa.String(length=255), server_default='Laws of India'),
        sa.Column('tags', sa.String(length=500), server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_contracts_organization_id', 'contracts', ['organization_id'])
    op.create_index('ix_contracts_contract_id', 'contracts', ['contract_id'])

    # 6. Contract Versions
    op.create_table(
        'contract_versions',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('contract_id', sa.String(length=36), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.String(length=20), nullable=False, server_default='v1.0'),
        sa.Column('filename', sa.String(length=255), nullable=True),
        sa.Column('file_storage_path', sa.String(length=500), nullable=False),
        sa.Column('file_mime_type', sa.String(length=100), nullable=False),
        sa.Column('file_byte_size', sa.Integer(), nullable=False),
        sa.Column('sha256_checksum', sa.String(length=64), nullable=False),
        sa.Column('page_count', sa.Integer(), server_default='1'),
        sa.Column('char_count', sa.Integer(), server_default='0'),
        sa.Column('word_count', sa.Integer(), server_default='0'),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('normalized_text', sa.Text(), nullable=True),
        sa.Column('parser_status', sa.String(length=50), server_default='COMPLETED'),
        sa.Column('processing_started_at', sa.String(length=50), nullable=True),
        sa.Column('processing_completed_at', sa.String(length=50), nullable=True),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=255), server_default='System'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_contract_versions_contract_id', 'contract_versions', ['contract_id'])

    # 7. Contract Clauses
    op.create_table(
        'contract_clauses',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('contract_id', sa.String(length=36), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('contract_version_id', sa.String(length=36), nullable=True),
        sa.Column('clause_title', sa.String(length=255), nullable=False),
        sa.Column('section_number', sa.String(length=50), server_default='Section 1.0'),
        sa.Column('original_text', sa.Text(), nullable=False),
        sa.Column('plain_language', sa.Text(), nullable=False),
        sa.Column('why_it_matters', sa.Text(), nullable=False),
        sa.Column('potential_concern', sa.Text(), nullable=True),
        sa.Column('suggested_action', sa.Text(), nullable=True),
        sa.Column('risk_level', sa.String(length=20), server_default='LOW'),
        sa.Column('category', sa.String(length=100), server_default='General'),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('position_order', sa.Integer(), server_default='0'),
        sa.Column('start_pos', sa.Integer(), nullable=True),
        sa.Column('end_pos', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_contract_clauses_contract_id', 'contract_clauses', ['contract_id'])

    # 8. Contract Risks
    op.create_table(
        'contract_risks',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('contract_id', sa.String(length=36), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('contract_version_id', sa.String(length=36), nullable=True),
        sa.Column('clause_id', sa.String(length=36), nullable=True),
        sa.Column('section_number', sa.String(length=50), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=False, server_default='LOW'),
        sa.Column('risk_title', sa.String(length=255), nullable=False),
        sa.Column('potential_impact', sa.Text(), nullable=False),
        sa.Column('remedy_recommendation', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=30), server_default='OPEN'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_contract_risks_contract_id', 'contract_risks', ['contract_id'])

    # 9. Contract Approval Steps
    op.create_table(
        'contract_approval_steps',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('contract_id', sa.String(length=36), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('role', sa.String(length=100), nullable=False),
        sa.Column('assigned_user', sa.String(length=255), nullable=False),
        sa.Column('decision', sa.String(length=20), server_default='PENDING'),
        sa.Column('decided_at', sa.String(length=50), nullable=True),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_contract_approval_steps_contract_id', 'contract_approval_steps', ['contract_id'])

    # 10. Contract Redlines
    op.create_table(
        'contract_redlines',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('contract_id', sa.String(length=36), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('clause_id', sa.String(length=36), nullable=True),
        sa.Column('section_title', sa.String(length=255), nullable=False),
        sa.Column('original_text', sa.Text(), nullable=False),
        sa.Column('suggested_text', sa.Text(), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='PENDING'),
        sa.Column('author', sa.String(length=255), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_contract_redlines_contract_id', 'contract_redlines', ['contract_id'])

    # 11. Refresh Tokens
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('family_id', sa.String(length=36), nullable=False),
        sa.Column('family_created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('created_ip', sa.String(length=50), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])
    op.create_index('ix_refresh_tokens_token_hash', 'refresh_tokens', ['token_hash'])
    op.create_index('ix_refresh_tokens_family_id', 'refresh_tokens', ['family_id'])

    # 12. Audit Logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), nullable=True),
        sa.Column('user_email', sa.String(length=255), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('object_type', sa.String(length=50), nullable=False),
        sa.Column('object_id', sa.String(length=100), nullable=False),
        sa.Column('detail', sa.Text(), nullable=False),
        sa.Column('ip_address', sa.String(length=50), server_default='127.0.0.1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_audit_logs_organization_id', 'audit_logs', ['organization_id'])

    # 13. Obligations
    op.create_table(
        'obligations',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('contract_id', sa.String(length=36), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('obligor_party', sa.String(length=255), nullable=False),
        sa.Column('obligee_party', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('due_date', sa.String(length=20), nullable=True),
        sa.Column('frequency', sa.String(length=30), server_default='ONE_TIME'),
        sa.Column('penalty_clause', sa.String(length=255), nullable=True),
        sa.Column('responsible_owner', sa.String(length=255), server_default='Contract Manager'),
        sa.Column('clause_id', sa.String(length=36), nullable=True),
        sa.Column('contract_version_id', sa.String(length=36), nullable=True),
        sa.Column('source_text', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='UPCOMING'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_obligations_contract_id', 'obligations', ['contract_id'])

    # 14. Obligation Evidence
    op.create_table(
        'obligation_evidence',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('obligation_id', sa.String(length=36), sa.ForeignKey('obligations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_storage_path', sa.String(length=500), nullable=False),
        sa.Column('uploaded_by', sa.String(length=255), server_default='Current User'),
        sa.Column('status', sa.String(length=30), server_default='UNDER_REVIEW'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_obligation_evidence_obligation_id', 'obligation_evidence', ['obligation_id'])

    # 15. Calendar Events
    op.create_table(
        'calendar_events',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('contract_id', sa.String(length=36), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=True),
        sa.Column('obligation_id', sa.String(length=36), sa.ForeignKey('obligations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False, server_default='CUSTOM_DATE'),
        sa.Column('event_date', sa.String(length=20), nullable=False),
        sa.Column('priority', sa.String(length=20), nullable=False, server_default='IMPORTANT'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='UPCOMING'),
        sa.Column('source_type', sa.String(length=50), nullable=False, server_default='USER_CUSTOM'),
        sa.Column('is_verified', sa.Boolean(), server_default='1'),
        sa.Column('is_important', sa.Boolean(), server_default='0'),
        sa.Column('created_by_user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_calendar_events_organization_id', 'calendar_events', ['organization_id'])
    op.create_index('ix_calendar_events_contract_id', 'calendar_events', ['contract_id'])
    op.create_index('ix_calendar_events_obligation_id', 'calendar_events', ['obligation_id'])
    op.create_index('ix_calendar_events_event_type', 'calendar_events', ['event_type'])
    op.create_index('ix_calendar_events_event_date', 'calendar_events', ['event_date'])

    # 16. Contract Notes
    op.create_table(
        'contract_notes',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('contract_id', sa.String(length=36), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('author_user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('author_name', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('reminder_date', sa.String(length=20), nullable=True),
        sa.Column('is_important', sa.Boolean(), server_default='0'),
        sa.Column('calendar_event_id', sa.String(length=36), sa.ForeignKey('calendar_events.id', ondelete='SET NULL'), nullable=True),
        sa.Column('obligation_id', sa.String(length=36), sa.ForeignKey('obligations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_contract_notes_organization_id', 'contract_notes', ['organization_id'])
    op.create_index('ix_contract_notes_contract_id', 'contract_notes', ['contract_id'])
    op.create_index('ix_contract_notes_author_user_id', 'contract_notes', ['author_user_id'])

    # 17. Vendors
    op.create_table(
        'vendors',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('contact_email', sa.String(length=255), nullable=False),
        sa.Column('contract_count', sa.Integer(), server_default='0'),
        sa.Column('total_contract_value', sa.Numeric(precision=15, scale=2), server_default='0.0'),
        sa.Column('risk_rating', sa.String(length=20), server_default='LOW'),
        sa.Column('compliance_rating', sa.Integer(), server_default='100'),
        sa.Column('sla_performance', sa.String(length=100), server_default='100% Target Met'),
        sa.Column('open_obligations', sa.Integer(), server_default='0'),
        sa.Column('critical_issues', sa.Integer(), server_default='0'),
        sa.Column('soc2_certified', sa.Boolean(), server_default='0'),
        sa.Column('gdpr_compliant', sa.Boolean(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_vendors_organization_id', 'vendors', ['organization_id'])

    # 18. Playbook Rules
    op.create_table(
        'playbook_rules',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('preferred_standard', sa.Text(), nullable=False),
        sa.Column('fallback_acceptable', sa.Text(), nullable=False),
        sa.Column('prohibited_terms', sa.Text(), server_default=''),
        sa.Column('negotiation_guidance', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_playbook_rules_organization_id', 'playbook_rules', ['organization_id'])

    # 19. Notifications
    op.create_table(
        'notifications',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('contract_id', sa.String(length=36), sa.ForeignKey('contracts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('obligation_id', sa.String(length=36), sa.ForeignKey('obligations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('calendar_event_id', sa.String(length=36), sa.ForeignKey('calendar_events.id', ondelete='SET NULL'), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('priority', sa.String(length=20), nullable=False, server_default='IMPORTANT'),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('delivery_channel', sa.String(length=20), server_default='IN_APP'),
        sa.Column('delivery_status', sa.String(length=20), server_default='SENT'),
        sa.Column('is_read', sa.Boolean(), server_default='0'),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('provider_message_id', sa.String(length=255), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('deduplication_key', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_notifications_organization_id', 'notifications', ['organization_id'])
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])
    op.create_index('ix_notifications_contract_id', 'notifications', ['contract_id'])
    op.create_index('ix_notifications_is_read', 'notifications', ['is_read'])
    op.create_index('ix_notifications_deduplication_key', 'notifications', ['deduplication_key'], unique=True)

    # 20. User Notification Preferences
    op.create_table(
        'user_notification_preferences',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email_notifications_enabled', sa.Boolean(), server_default='0'),
        sa.Column('renewal_reminders', sa.Boolean(), server_default='1'),
        sa.Column('notice_deadline_reminders', sa.Boolean(), server_default='1'),
        sa.Column('obligation_reminders', sa.Boolean(), server_default='1'),
        sa.Column('approval_reminders', sa.Boolean(), server_default='1'),
        sa.Column('critical_events_enabled', sa.Boolean(), server_default='1'),
        sa.Column('reminder_intervals_json', sa.String(length=255), server_default='[30, 7, 1]'),
        sa.Column('daily_notification_limit', sa.Integer(), server_default='10'),
        sa.Column('quiet_hours_enabled', sa.Boolean(), server_default='0'),
        sa.Column('quiet_hours_start', sa.String(length=10), server_default='22:00'),
        sa.Column('quiet_hours_end', sa.String(length=10), server_default='08:00'),
        sa.Column('preferred_notification_email', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('organization_id', 'user_id', name='uq_org_user_preference')
    )
    op.create_index('ix_user_notification_preferences_organization_id', 'user_notification_preferences', ['organization_id'])
    op.create_index('ix_user_notification_preferences_user_id', 'user_notification_preferences', ['user_id'])


def downgrade() -> None:
    op.drop_table('user_notification_preferences')
    op.drop_table('notifications')
    op.drop_table('playbook_rules')
    op.drop_table('vendors')
    op.drop_table('contract_notes')
    op.drop_table('calendar_events')
    op.drop_table('obligation_evidence')
    op.drop_table('obligations')
    op.drop_table('audit_logs')
    op.drop_table('refresh_tokens')
    op.drop_table('contract_redlines')
    op.drop_table('contract_approval_steps')
    op.drop_table('contract_risks')
    op.drop_table('contract_clauses')
    op.drop_table('contract_versions')
    op.drop_table('contracts')
    op.drop_table('organization_members')
    op.drop_table('users')
    op.drop_table('departments')
    op.drop_table('organizations')

"""
Regression test suite for Phase N:
Evidence-based end-to-end verification of Email Delivery,
Both Chatbot Experiences, and Grounded Contract Intelligence.
"""

import uuid
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.config import settings
from app.models.organization import Organization
from app.models.user import User, OrganizationMember
from app.models.contract import Contract, ContractClause, ContractRisk
from app.models.notification import Notification, UserNotificationPreference
from app.core.security import get_password_hash, create_access_token
from app.services.email.provider import (
    DisabledEmailProvider,
    SMTPEmailProvider,
    EmailDeliveryResult,
    get_email_provider
)
from app.services.notifications.dispatcher import NotificationDispatcher
from app.services.notifications.policy import NotificationPriority
from app.services.ai.gemini_provider import (
    GeminiProvider,
    GeminiConfigurationError,
    GeminiProviderError,
    sanitize_error_detail
)
from app.services.ai.prompts import (
    CONTRACT_QA_SYSTEM_PROMPT,
    GENERAL_ASSISTANT_SYSTEM_PROMPT,
    GROUNDED_FALLBACK_ANSWER
)
from app.services.ai.contract_qa import ask_contract_qa
from app.services.ai.general_assistant import ask_contractly_chat


# Helper to set up two isolated tenants with users
async def _setup_tenants_and_contract(test_engine):
    TestSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False
    )
    suffix = uuid.uuid4().hex[:6]
    async with TestSessionLocal() as session:
        # Tenant A
        org_a = Organization(
            name=f"Tenant A {suffix}",
            slug=f"tenant-a-{suffix}",
            account_type="BUSINESS"
        )
        session.add(org_a)
        await session.flush()

        user_a = User(
            email=f"user-a-{suffix}@internal.test",
            password_hash=get_password_hash("Password123!"),
            full_name=f"User A {suffix}"
        )
        session.add(user_a)
        await session.flush()

        member_a = OrganizationMember(
            organization_id=org_a.id,
            user_id=user_a.id,
            role="LEGAL_MANAGER",
            status="ACTIVE"
        )
        session.add(member_a)

        # Contract under Tenant A
        c_a = Contract(
            organization_id=org_a.id,
            contract_id=f"CTR-A-{suffix}",
            title=f"SaaS Agreement A {suffix}",
            counterparty="Vendor Alpha",
            contract_type="Software License",
            status="ACTIVE",
            start_date="2026-01-01",
            expiry_date="2027-01-01",
            renewal_date="2026-11-01",
            auto_renew=True,
            renewal_notice_days=60,
            termination_notice_days=30,
            governing_law="State of California"
        )
        session.add(c_a)
        await session.flush()

        clause1 = ContractClause(
            contract_id=c_a.id,
            section_number="Section 3.1",
            clause_title="Governing Law",
            original_text="This Agreement shall be governed by and construed under the laws of the State of California.",
            plain_language="Governed by California state law.",
            why_it_matters="Dictates governing jurisdiction.",
            category="GOVERNING_LAW",
            page_number=2
        )
        session.add(clause1)

        # Tenant B
        org_b = Organization(
            name=f"Tenant B {suffix}",
            slug=f"tenant-b-{suffix}",
            account_type="BUSINESS"
        )
        session.add(org_b)
        await session.flush()

        user_b = User(
            email=f"user-b-{suffix}@internal.test",
            password_hash=get_password_hash("Password123!"),
            full_name=f"User B {suffix}"
        )
        session.add(user_b)
        await session.flush()

        member_b = OrganizationMember(
            organization_id=org_b.id,
            user_id=user_b.id,
            role="LEGAL_MANAGER",
            status="ACTIVE"
        )
        session.add(member_b)

        await session.commit()

        token_a = create_access_token(subject=user_a.id, org_id=org_a.id, role="LEGAL_MANAGER")
        token_b = create_access_token(subject=user_b.id, org_id=org_b.id, role="LEGAL_MANAGER")

        return {
            "org_a": org_a,
            "user_a": user_a,
            "contract_a": c_a,
            "token_a": token_a,
            "org_b": org_b,
            "user_b": user_b,
            "token_b": token_b,
        }


# ==============================================================================
# SECTION A: EMAIL DELIVERY VERIFICATION TESTS
# ==============================================================================

def test_disabled_email_provider_fidelity():
    """DisabledEmailProvider must report success=False truthfully without claiming delivery."""
    provider = DisabledEmailProvider()
    res = provider.send_email(
        to_email="test@example.com",
        subject="Test Alert",
        html_body="<p>Test</p>",
        text_body="Test"
    )
    assert res.success is False
    assert "disabled" in res.error_message.lower()
    assert res.provider_message_id is None


def test_smtp_provider_missing_host():
    """SMTPEmailProvider without host must fail safely without raising unhandled exceptions."""
    provider = SMTPEmailProvider(host="")
    res = provider.send_email(
        to_email="test@example.com",
        subject="Test Alert",
        html_body="<p>Test</p>",
        text_body="Test"
    )
    assert res.success is False
    assert "SMTP_HOST is not configured" in res.error_message


@pytest.mark.asyncio
async def test_notification_dispatcher_skips_duplicate(test_engine):
    """NotificationDispatcher must prevent duplicate deliveries via deduplication keys."""
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    data = await _setup_tenants_and_contract(test_engine)

    dedup_key = f"test-dedup-{uuid.uuid4().hex}"
    async with TestSessionLocal() as session:
        # First dispatch
        notif1, status1 = await NotificationDispatcher.dispatch_notification(
            db=session,
            organization_id=data["org_a"].id,
            user_id=data["user_a"].id,
            title="Renewal Notice",
            message="Contract renewal due soon.",
            event_type="RENEWAL_NOTICE",
            priority=NotificationPriority.CRITICAL,
            deduplication_key=dedup_key
        )
        assert notif1 is not None
        assert status1 == "DELIVERED"

        # Second dispatch with identical key
        notif2, status2 = await NotificationDispatcher.dispatch_notification(
            db=session,
            organization_id=data["org_a"].id,
            user_id=data["user_a"].id,
            title="Renewal Notice Duplicate",
            message="Contract renewal due soon.",
            event_type="RENEWAL_NOTICE",
            priority=NotificationPriority.CRITICAL,
            deduplication_key=dedup_key
        )
        assert notif2 is None
        assert status2 == "SKIPPED_DEDUPLICATION"


# ==============================================================================
# SECTION B: CHATBOT SECURITY & ERROR HANDLING
# ==============================================================================

def test_sanitize_error_detail_strips_api_keys():
    """Secrets, API keys, and internal traces must never leak into client-facing error details."""
    raw_error = "Failed to authenticate with Gemini: invalid key AIzaSyA1234567890abcdef at https://generativelanguage.googleapis.com"
    sanitized = sanitize_error_detail(raw_error)
    assert "AIza" not in sanitized
    assert "googleapis.com" not in sanitized
    assert "[REDACTED]" in sanitized


def test_general_assistant_prompt_isolation():
    """General assistant system prompt must define strict boundary and lack contract database access."""
    assert "General Contract Operations and CLM Assistant" in GENERAL_ASSISTANT_SYSTEM_PROMPT
    assert "You do not have access to a specific executed contract" in GENERAL_ASSISTANT_SYSTEM_PROMPT
    assert "You are NOT an attorney and do not provide legal advice" in GENERAL_ASSISTANT_SYSTEM_PROMPT


# ==============================================================================
# SECTION C: GROUNDED CONTRACT Q&A & TENANT ISOLATION
# ==============================================================================

@pytest.mark.asyncio
async def test_grounded_contract_qa_fallback_on_absent_facts():
    """Contract Q&A must return grounded fallback when asked about information absent from document."""
    mock_provider = MagicMock(spec=GeminiProvider)
    c = Contract(
        id=str(uuid.uuid4()),
        organization_id=str(uuid.uuid4()),
        contract_id="CTR-TEST",
        title="Sample NDA",
        counterparty="Vendor",
        contract_type="NDA"
    )
    c.clauses = []
    c.risks = []
    c.obligations = []

    # Irrelevant question
    res = await ask_contract_qa(c, "What is the penalty for delayed shipping of widgets?", provider=mock_provider)
    assert res.answer == GROUNDED_FALLBACK_ANSWER
    assert res.sources == []
    # Mock provider should not even be invoked since retrieval returned empty context
    assert mock_provider.generate_content.call_count == 0


@pytest.mark.asyncio
async def test_cross_tenant_contract_qa_rejected(test_engine):
    """User in Tenant B must receive 404 when attempting to query a contract belonging to Tenant A."""
    data = await _setup_tenants_and_contract(test_engine)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # User B queries Contract A
        res = await ac.post(
            f"/api/v1/contracts/{data['contract_a'].id}/qa",
            headers={"Authorization": f"Bearer {data['token_b']}"},
            json={"question": "What is the governing law of this contract?"}
        )
        assert res.status_code == 404
        assert res.json()["detail"] == "Contract not found."


@pytest.mark.asyncio
async def test_contract_qa_invalid_contract_id_returns_404(test_engine):
    """Querying a non-existent contract ID must return 404."""
    data = await _setup_tenants_and_contract(test_engine)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            f"/api/v1/contracts/{uuid.uuid4()}/qa",
            headers={"Authorization": f"Bearer {data['token_a']}"},
            json={"question": "What is the governing law?"}
        )
        assert res.status_code == 404
        assert res.json()["detail"] == "Contract not found."

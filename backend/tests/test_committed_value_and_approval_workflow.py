import pytest
import uuid
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy.future import select

from app.main import app
from app.core.security import get_password_hash, create_access_token
from app.models.organization import Organization
from app.models.user import User, OrganizationMember
from app.models.contract import Contract, ContractVersion, ContractApprovalStep
from app.services.intelligence.financial_extractor import (
    extract_contract_financials,
    extract_term_months_from_text,
    parse_numeric_amount
)


async def _setup_tenant_user(test_engine, name_prefix: str, role: str = "OWNER"):
    suffix = uuid.uuid4().hex[:8]
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        org = Organization(name=f"{name_prefix} Org {suffix}", slug=f"{name_prefix.lower()}-{suffix}")
        session.add(org)
        await session.flush()

        user = User(
            email=f"{name_prefix.lower()}_{suffix}@example.com",
            password_hash=get_password_hash("Password123!"),
            full_name=f"{name_prefix} User"
        )
        session.add(user)
        await session.flush()

        member = OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role=role,
            status="ACTIVE"
        )
        session.add(member)
        await session.commit()

        token = create_access_token(subject=user.id, org_id=org.id, role=role)
        return org, user, token


# ==============================================================================
# ISSUE 1 TESTS: MONETARY VALUE EXTRACTION & COMMITTED VALUE NORMALIZATION
# ==============================================================================

def test_financial_extractor_recurring_plus_onetime():
    """
    Test Requirement 1:
    One-time implementation fee: INR 50,000
    Recurring service fee: INR 25,000 per month
    Initial term: 12 months
    Expected initial-term value: INR 350,000 (50,000 + 25,000 * 12).
    """
    text = """
    MASTER CLOUD SERVICES AGREEMENT
    1. Scope of Services
    Vendor shall provide managed enterprise analytics services.
    2. Fees and Invoicing
    One-time implementation fee: INR 50,000 payable upon signing.
    Recurring service fee: INR 25,000 per month payable in advance.
    3. Term and Renewal
    The initial term of this Agreement is 12 months from the Effective Date.
    """
    res = extract_contract_financials(text)
    assert res["value"] == 350000.0
    assert res["currency"] == "INR"
    assert res["value_basis"] == "CALCULATED_TERM"
    assert res["is_verified"] is True
    assert "INR 50,000" in res["calculation_explanation"]
    assert "INR 25,000/month" in res["calculation_explanation"]
    assert "12 months" in res["calculation_explanation"]


def test_financial_extractor_fixed_total_preferred():
    """
    Test Requirement 2:
    A fixed total value is preferred over recomputing it from individual clauses when appropriate.
    """
    text = """
    SOFTWARE DEVELOPMENT AGREEMENT
    Payment Terms
    The Client shall pay the Service Provider a total contract value of ₹4,80,000.
    Milestone disbursements:
    - Milestone 1: ₹1,60,000
    - Milestone 2: ₹1,60,000
    - Final delivery: ₹1,60,000
    Initial term: 12 months
    """
    res = extract_contract_financials(text)
    assert res["value"] == 480000.0
    assert res["currency"] == "INR"
    assert res["value_basis"] == "FIXED_TOTAL"
    assert res["is_verified"] is True


def test_financial_extractor_ambiguous_term_duration():
    """
    Test Requirement 3:
    Missing or ambiguous term duration does not produce a fabricated total.
    """
    text = """
    SUBSCRIPTION SERVICES ADDENDUM
    Recurring service fee: INR 25,000 per month.
    Either party may terminate at any time upon reasonable notice.
    """
    res = extract_contract_financials(text)
    assert res["value"] is None
    assert res["value_basis"] == "NEEDS_VERIFICATION"
    assert res["is_verified"] is False
    assert "ambiguous" in res["calculation_explanation"].lower()


def test_financial_extractor_genuine_zero_distinguished():
    """
    Test Requirement 4:
    A genuine zero is distinguished from an unknown value.
    """
    text_zero = """
    MUTUAL NON-DISCLOSURE AGREEMENT
    The parties agree to disclose confidential information without monetary consideration or fee.
    """
    res_zero = extract_contract_financials(text_zero)
    assert res_zero["value"] == 0.0
    assert res_zero["value_basis"] == "GENUINE_ZERO"
    assert res_zero["is_verified"] is True

    text_unknown = """
    MUTUAL NON-DISCLOSURE AGREEMENT
    Each party agrees to maintain strict confidentiality of proprietary specifications.
    Term: 2 years.
    """
    res_unknown = extract_contract_financials(text_unknown)
    assert res_unknown["value"] is None
    assert res_unknown["value_basis"] == "NOT_SPECIFIED"
    assert res_unknown["is_verified"] is False


def test_financial_extractor_conflicting_currencies_not_mixed():
    """
    Test Requirement 5:
    Different currencies are not incorrectly summed.
    """
    text_mixed = """
    CROSS-BORDER INTEGRATION SCHEDULE
    Setup Fee: USD 5,000.
    Ongoing Maintenance: INR 50,000 per month.
    Initial Term: 12 months.
    """
    res_mixed = extract_contract_financials(text_mixed)
    assert res_mixed["value"] is None
    assert res_mixed["value_basis"] == "NEEDS_VERIFICATION"
    assert "conflicting currencies" in res_mixed["calculation_explanation"].lower()


def test_financial_extractor_ignores_liability_caps_and_penalties():
    """
    Verifies that liability caps, liquidated damages, and penalty clauses
    are NEVER mistaken for committed contract values.
    """
    text = """
    HOSTED SERVICE AGREEMENT
    Annual Subscription Fee: INR 12,00,000 payable annually.
    Initial term: 12 months.
    Limitation of Liability:
    VENDOR'S TOTAL AGGREGATE LIABILITY UNDER THIS AGREEMENT SHALL NOT EXCEED INR 50,000.
    Penalty:
    Delay penalty of INR 10,000 per calendar day applies to late delivery.
    """
    res = extract_contract_financials(text)
    assert res["value"] == 1200000.0
    assert res["currency"] == "INR"
    assert res["value_basis"] == "CALCULATED_TERM"


@pytest.mark.asyncio
async def test_existing_records_without_monetary_metadata_load_safely(test_engine):
    """
    Test Requirement 8:
    Existing records without monetary metadata continue to load safely.
    """
    org, user, token = await _setup_tenant_user(test_engine, "SafeLoadOrg", role="LEGAL_MANAGER")
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSessionLocal() as session:
        contract = Contract(
            organization_id=org.id,
            contract_id=f"CTR-TEST-{uuid.uuid4().hex[:4]}",
            title="Non-Monetary Governance Agreement",
            contract_type="Governance Agreement",
            counterparty="Partner Alliance",
            value=None,
            currency="INR",
            value_basis="NOT_SPECIFIED",
            calculation_explanation=None,
            status="UNDER_REVIEW"
        )
        session.add(contract)
        await session.commit()
        contract_id = contract.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {token}"}
        res = await client.get(f"/api/v1/contracts/{contract_id}", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == contract_id
        assert data["value"] is None
        assert data["value_basis"] == "NOT_SPECIFIED"


# ==============================================================================
# ISSUE 2 TESTS: APPROVAL WORKFLOW VERIFICATION
# ==============================================================================

@pytest.mark.asyncio
async def test_approval_workflow_enforces_sequential_order(test_engine):
    """
    Confirms:
    1. Each contract has the correct ordered approval steps.
    2. A later step cannot be approved before prerequisite steps are complete.
    """
    org, user, token = await _setup_tenant_user(test_engine, "SequentialOrg", role="LEGAL_MANAGER")
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSessionLocal() as session:
        contract = Contract(
            organization_id=org.id,
            contract_id=f"CTR-APP-{uuid.uuid4().hex[:4]}",
            title="Procurement Services Agreement",
            contract_type="Services",
            counterparty="FastTrack Logistics",
            value=350000.0,
            currency="INR",
            value_basis="CALCULATED_TERM",
            status="UNDER_REVIEW"
        )
        session.add(contract)
        await session.flush()

        step1 = ContractApprovalStep(
            contract_id=contract.id,
            step_order=1,
            role="Department Lead",
            assigned_user=user.full_name,
            decision="PENDING"
        )
        step2 = ContractApprovalStep(
            contract_id=contract.id,
            step_order=2,
            role="Legal Manager",
            assigned_user="Legal Team",
            decision="PENDING"
        )
        session.add(step1)
        session.add(step2)
        await session.commit()
        contract_id = contract.id
        step1_id = step1.id
        step2_id = step2.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {token}"}

        # Step 2 cannot be approved before Step 1
        res_step2 = await client.post(
            f"/api/v1/contracts/{contract_id}/approvals/{step2_id}/decision",
            json={"decision": "APPROVED", "comments": "Premature review"},
            headers=headers
        )
        assert res_step2.status_code == 400
        assert "Prior step 1 is still PENDING" in res_step2.json()["detail"]

        # Step 1 approval succeeds
        res_step1 = await client.post(
            f"/api/v1/contracts/{contract_id}/approvals/{step1_id}/decision",
            json={"decision": "APPROVED", "comments": "Department verified"},
            headers=headers
        )
        assert res_step1.status_code == 200
        assert res_step1.json()["decision"] == "APPROVED"

        # Step 2 approval succeeds after Step 1
        res_step2_ok = await client.post(
            f"/api/v1/contracts/{contract_id}/approvals/{step2_id}/decision",
            json={"decision": "APPROVED", "comments": "Legal cleared"},
            headers=headers
        )
        assert res_step2_ok.status_code == 200
        assert res_step2_ok.json()["decision"] == "APPROVED"

        # Contract transitions to APPROVED (NOT SIGNED or EXECUTED)
        res_c = await client.get(f"/api/v1/contracts/{contract_id}", headers=headers)
        assert res_c.json()["status"] == "APPROVED"
        assert res_c.json()["status"] not in ("SIGNED", "EXECUTED", "ACTIVE")


@pytest.mark.asyncio
async def test_approval_workflow_unauthorized_user_blocked(test_engine):
    """
    Confirms:
    3. Unauthorized users cannot decide approval steps (HTTP 403).
    """
    org, owner_user, owner_token = await _setup_tenant_user(test_engine, "AuthOrg", role="OWNER")
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    # Create a non-authorized member (MEMBER role does not have approvals:decide)
    async with TestSessionLocal() as session:
        unauth_user = User(
            email=f"member_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=get_password_hash("Password123!"),
            full_name="Basic Member"
        )
        session.add(unauth_user)
        await session.flush()

        member = OrganizationMember(
            organization_id=org.id,
            user_id=unauth_user.id,
            role="MEMBER",
            status="ACTIVE"
        )
        session.add(member)

        contract = Contract(
            organization_id=org.id,
            contract_id=f"CTR-AUTH-{uuid.uuid4().hex[:4]}",
            title="SaaS Subscription",
            contract_type="Subscription",
            counterparty="AuthCloud",
            status="UNDER_REVIEW"
        )
        session.add(contract)
        await session.flush()

        step1 = ContractApprovalStep(
            contract_id=contract.id,
            step_order=1,
            role="Finance Lead",
            assigned_user="Finance Lead",
            decision="PENDING"
        )
        session.add(step1)
        await session.commit()

        contract_id = contract.id
        step1_id = step1.id
        unauth_token = create_access_token(subject=unauth_user.id, org_id=org.id, role="MEMBER")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/contracts/{contract_id}/approvals/{step1_id}/decision",
            json={"decision": "APPROVED", "comments": "Unauthorized bypass attempt"},
            headers={"Authorization": f"Bearer {unauth_token}"}
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_approval_workflow_repeated_and_terminal_blocked(test_engine):
    """
    Confirms:
    9. Repeated requests cannot bypass the workflow (already decided step cannot be re-decided).
    """
    org, user, token = await _setup_tenant_user(test_engine, "RepeatOrg", role="OWNER")
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSessionLocal() as session:
        contract = Contract(
            organization_id=org.id,
            contract_id=f"CTR-REP-{uuid.uuid4().hex[:4]}",
            title="Cloud Agreement",
            contract_type="Services",
            counterparty="ServerVendor",
            status="UNDER_REVIEW"
        )
        session.add(contract)
        await session.flush()

        step = ContractApprovalStep(
            contract_id=contract.id,
            step_order=1,
            role="Manager",
            assigned_user=user.full_name,
            decision="PENDING"
        )
        session.add(step)
        await session.commit()
        contract_id = contract.id
        step_id = step.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {token}"}

        # First approval succeeds
        res1 = await client.post(
            f"/api/v1/contracts/{contract_id}/approvals/{step_id}/decision",
            json={"decision": "APPROVED", "comments": "First signoff"},
            headers=headers
        )
        assert res1.status_code == 200

        # Repeated approval request fails with HTTP 400
        res2 = await client.post(
            f"/api/v1/contracts/{contract_id}/approvals/{step_id}/decision",
            json={"decision": "APPROVED", "comments": "Repeated signoff"},
            headers=headers
        )
        assert res2.status_code == 400
        assert "already been decided" in res2.json()["detail"]

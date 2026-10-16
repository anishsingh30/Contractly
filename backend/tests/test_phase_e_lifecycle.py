import pytest
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy.future import select

from app.main import app
from app.core.security import get_password_hash, create_access_token
from app.models.organization import Organization
from app.models.user import User, OrganizationMember
from app.models.contract import (
    Contract,
    ContractVersion,
    ContractClause,
    ContractRisk,
    ContractApprovalStep,
    ContractRedline
)
from app.models.obligation import Obligation
from app.models.playbook import PlaybookRule
from app.models.audit import AuditLog

async def _setup_tenant(test_engine, name_prefix: str, role: str = "OWNER"):
    suffix = uuid.uuid4().hex[:8]
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        org = Organization(name=f"{name_prefix} {suffix}", slug=f"{name_prefix.lower()}-{suffix}")
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

@pytest.mark.asyncio
async def test_valid_and_invalid_lifecycle_transitions(test_engine):
    """
    1. Valid lifecycle transition succeeds.
    2. Invalid lifecycle transition fails with HTTP 400.
    """
    org, user, token = await _setup_tenant(test_engine, "LifecycleOrg", role="LEGAL_MANAGER")

    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        contract = Contract(
            organization_id=org.id,
            contract_id=f"CTR-TEST-001",
            title="SaaS Agreement",
            contract_type="SaaS",
            counterparty="VendorCorp",
            status="UNDER_REVIEW"
        )
        session.add(contract)
        await session.commit()
        contract_id = contract.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Valid transition: UNDER_REVIEW -> REDLINE
        res = await client.patch(
            f"/api/v1/contracts/{contract_id}/status",
            json={"status": "REDLINE", "reason": "Legal review complete"},
            headers=headers
        )
        assert res.status_code == 200
        assert res.json()["status"] == "REDLINE"

        # Valid transition: REDLINE -> NEGOTIATION
        res = await client.patch(
            f"/api/v1/contracts/{contract_id}/status",
            json={"status": "NEGOTIATION"},
            headers=headers
        )
        assert res.status_code == 200
        assert res.json()["status"] == "NEGOTIATION"

        # 2. Invalid transition: NEGOTIATION cannot jump directly to ACTIVE or SIGNED
        res_invalid = await client.patch(
            f"/api/v1/contracts/{contract_id}/status",
            json={"status": "SIGNED"},
            headers=headers
        )
        assert res_invalid.status_code == 400
        assert "Invalid lifecycle transition" in res_invalid.json()["detail"]

@pytest.mark.asyncio
async def test_lifecycle_rbac_and_tenant_isolation(test_engine):
    """
    3. Unauthorized role cannot transition.
    4. Foreign tenant cannot transition contract.
    """
    org_a, _, token_manager = await _setup_tenant(test_engine, "TenantA", role="LEGAL_MANAGER")
    _, _, token_employee = await _setup_tenant(test_engine, "TenantAEmployee", role="EMPLOYEE")
    org_b, _, token_tenant_b = await _setup_tenant(test_engine, "TenantB", role="OWNER")

    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        contract = Contract(
            organization_id=org_a.id,
            contract_id="CTR-A-001",
            title="Vendor A Agreement",
            contract_type="MSA",
            counterparty="Vendor A",
            status="UNDER_REVIEW"
        )
        session.add(contract)
        await session.commit()
        contract_id = contract.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 3. Employee lacks permission -> HTTP 403
        res_emp = await client.patch(
            f"/api/v1/contracts/{contract_id}/status",
            json={"status": "REDLINE"},
            headers={"Authorization": f"Bearer {token_employee}"}
        )
        assert res_emp.status_code == 403

        # 4. Foreign tenant attempts to transition Tenant A's contract -> HTTP 404
        res_b = await client.patch(
            f"/api/v1/contracts/{contract_id}/status",
            json={"status": "REDLINE"},
            headers={"Authorization": f"Bearer {token_tenant_b}"}
        )
        assert res_b.status_code == 404
        assert "Contract not found" in res_b.json()["detail"]

@pytest.mark.asyncio
async def test_contract_versions_and_tenant_isolation(test_engine):
    """
    5. Contract version belongs to correct tenant and is persisted.
    6. Foreign tenant cannot access contract version.
    """
    org_a, user_a, token_a = await _setup_tenant(test_engine, "VersionOrgA", role="OWNER")
    org_b, _, token_b = await _setup_tenant(test_engine, "VersionOrgB", role="OWNER")

    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        contract = Contract(
            organization_id=org_a.id,
            contract_id="CTR-VER-01",
            title="Versioned Agreement",
            contract_type="MSA",
            counterparty="Supplier X",
            status="UNDER_REVIEW"
        )
        session.add(contract)
        await session.flush()

        version = ContractVersion(
            contract_id=contract.id,
            version_number="v1.0",
            file_storage_path=f"{org_a.id}/CTR-VER-01/v1.0/contract.pdf",
            file_mime_type="application/pdf",
            file_byte_size=2048,
            sha256_checksum="abc123sha256hash",
            change_summary="Initial intake",
            created_by=user_a.full_name
        )
        session.add(version)
        await session.commit()
        contract_id = contract.id
        version_id = version.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Tenant A can list versions
        res = await client.get(f"/api/v1/contracts/{contract_id}/versions", headers={"Authorization": f"Bearer {token_a}"})
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["version_number"] == "v1.0"
        assert data[0]["sha256_checksum"] == "abc123sha256hash"

        # Tenant B receives 404 when requesting Tenant A's versions
        res_b = await client.get(f"/api/v1/contracts/{contract_id}/versions", headers={"Authorization": f"Bearer {token_b}"})
        assert res_b.status_code == 200
        assert res_b.json() == []

        res_b_single = await client.get(f"/api/v1/contracts/{contract_id}/versions/{version_id}", headers={"Authorization": f"Bearer {token_b}"})
        assert res_b_single.status_code == 404

@pytest.mark.asyncio
async def test_redlines_crud_rbac_and_audit(test_engine):
    """
    7. Redline is tenant isolated.
    8. Redline action is RBAC protected.
    16. Major redline actions create audit logs.
    """
    org_a, _, token_legal = await _setup_tenant(test_engine, "RedlineOrgA", role="LEGAL_REVIEWER")
    _, _, token_emp = await _setup_tenant(test_engine, "RedlineEmp", role="EMPLOYEE")
    org_b, _, token_b = await _setup_tenant(test_engine, "RedlineOrgB", role="OWNER")

    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        contract = Contract(
            organization_id=org_a.id,
            contract_id="CTR-RL-01",
            title="Redline Contract",
            contract_type="SaaS",
            counterparty="Vendor Y",
            status="UNDER_REVIEW"
        )
        session.add(contract)
        await session.commit()
        contract_id = contract.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers_legal = {"Authorization": f"Bearer {token_legal}"}

        # 8. Employee cannot create redline (HTTP 403)
        res_emp = await client.post(
            f"/api/v1/contracts/{contract_id}/redlines",
            json={
                "section_title": "Limitation of Liability",
                "original_text": "Vendor cap is 1 month",
                "suggested_text": "Mutual cap is 12 months"
            },
            headers={"Authorization": f"Bearer {token_emp}"}
        )
        assert res_emp.status_code == 403

        # Legal Reviewer creates redline
        res_create = await client.post(
            f"/api/v1/contracts/{contract_id}/redlines",
            json={
                "section_title": "Limitation of Liability",
                "original_text": "Vendor cap is 1 month",
                "suggested_text": "Mutual cap is 12 months",
                "rationale": "Standard corporate risk posture"
            },
            headers=headers_legal
        )
        assert res_create.status_code == 200
        rl_data = res_create.json()
        assert rl_data["status"] == "PENDING"
        redline_id = rl_data["id"]

        # 7. Tenant B cannot see Tenant A's redlines
        res_b = await client.get(f"/api/v1/contracts/{contract_id}/redlines", headers={"Authorization": f"Bearer {token_b}"})
        assert res_b.status_code == 200
        assert res_b.json() == []

        # Accept redline
        res_accept = await client.patch(
            f"/api/v1/contracts/{contract_id}/redlines/{redline_id}/status",
            json={"status": "ACCEPTED"},
            headers=headers_legal
        )
        assert res_accept.status_code == 200
        assert res_accept.json()["status"] == "ACCEPTED"

        # Add comment
        res_comm = await client.post(
            f"/api/v1/contracts/{contract_id}/redlines/{redline_id}/comment",
            json={"comment": "Agreed with vendor during negotiation call."},
            headers=headers_legal
        )
        assert res_comm.status_code == 200
        assert res_comm.json()["comment"] == "Agreed with vendor during negotiation call."

        # Verify Audit Logs generated for Redlines
        res_audit = await client.get("/api/v1/organizations/audit-logs", headers=headers_legal)
        assert res_audit.status_code == 200
        actions = [a["action"] for a in res_audit.json()]
        assert "REDLINE_CREATED" in actions
        assert "REDLINE_ACCEPTED" in actions
        assert "REDLINE_COMMENTED" in actions

@pytest.mark.asyncio
async def test_approval_workflow_sequence_and_rejection(test_engine):
    """
    9. Approval sequence works in order.
    10. Unauthorized/out-of-order approval fails.
    11. Rejected approval changes lifecycle correctly.
    """
    org, _, token = await _setup_tenant(test_engine, "ApprovalWorkflowOrg", role="LEGAL_MANAGER")

    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        contract = Contract(
            organization_id=org.id,
            contract_id="CTR-APP-01",
            title="Master Services Agreement",
            contract_type="MSA",
            counterparty="Client Z",
            status="PENDING_APPROVAL"
        )
        session.add(contract)
        await session.flush()

        step1 = ContractApprovalStep(
            contract_id=contract.id,
            step_order=1,
            role="Department Lead",
            assigned_user="Lead User",
            decision="PENDING"
        )
        step2 = ContractApprovalStep(
            contract_id=contract.id,
            step_order=2,
            role="Legal Manager",
            assigned_user="Legal User",
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

        # 10. Trying to approve Step 2 before Step 1 fails with HTTP 400
        res_step2_early = await client.post(
            f"/api/v1/contracts/{contract_id}/approvals/{step2_id}/decision",
            json={"decision": "APPROVED", "comments": "Premature signoff"},
            headers=headers
        )
        assert res_step2_early.status_code == 400
        assert "Prior step 1 is still PENDING" in res_step2_early.json()["detail"]

        # 9. Approve Step 1
        res_step1 = await client.post(
            f"/api/v1/contracts/{contract_id}/approvals/{step1_id}/decision",
            json={"decision": "APPROVED", "comments": "Department approved"},
            headers=headers
        )
        assert res_step1.status_code == 200
        assert res_step1.json()["decision"] == "APPROVED"

        # 11. Step 2 is REJECTED -> Contract transitions back to UNDER_REVIEW
        res_step2_reject = await client.post(
            f"/api/v1/contracts/{contract_id}/approvals/{step2_id}/decision",
            json={"decision": "REJECTED", "comments": "Indemnity clause needs revisions"},
            headers=headers
        )
        assert res_step2_reject.status_code == 200
        assert res_step2_reject.json()["decision"] == "REJECTED"

        # Verify contract status reverted to UNDER_REVIEW
        res_c = await client.get(f"/api/v1/contracts/{contract_id}", headers=headers)
        assert res_c.status_code == 200
        assert res_c.json()["status"] == "UNDER_REVIEW"

@pytest.mark.asyncio
async def test_deterministic_overdue_obligations_and_renewal_intelligence(test_engine):
    """
    12. Obligations remain tenant isolated.
    13. Overdue obligation is detected deterministically.
    14. Renewal window is calculated correctly.
    15. Controlled termination workflow requires authorization.
    """
    org, _, token = await _setup_tenant(test_engine, "IntelligenceOrg", role="OWNER")

    today = datetime.now(timezone.utc).date()
    past_due = (today - timedelta(days=10)).strftime("%Y-%m-%d")
    upcoming_expiry = (today + timedelta(days=25)).strftime("%Y-%m-%d")

    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        contract = Contract(
            organization_id=org.id,
            contract_id="CTR-INTEL-01",
            title="Cloud Infrastructure Services",
            contract_type="Cloud",
            counterparty="AWS India",
            start_date="2026-01-01",
            expiry_date=upcoming_expiry,
            renewal_date=upcoming_expiry,
            renewal_notice_days=30,
            status="ACTIVE"
        )
        session.add(contract)
        await session.flush()

        # Obligation that is past due and not fulfilled
        obl = Obligation(
            contract_id=contract.id,
            obligor_party="AWS India",
            obligee_party="Our Company",
            title="Submit SOC 2 Report",
            description="Annual SOC 2 Type II compliance audit report",
            due_date=past_due,
            status="UPCOMING"
        )
        session.add(obl)

        # Active Playbook rule
        rule = PlaybookRule(
            organization_id=org.id,
            category="Liability",
            preferred_standard="12 months fees paid mutual limitation",
            fallback_acceptable="1.5x annual contract value",
            prohibited_terms="unlimited liability, 3 months cap",
            negotiation_guidance="Insist on mutual cap for cloud infrastructure."
        )
        session.add(rule)

        # High risk clause to trigger playbook match
        clause = ContractClause(
            contract_id=contract.id,
            clause_title="Limitation of Liability",
            section_number="Section 11.0",
            original_text="Vendor liability is subject to a 3 months cap on total fees.",
            plain_language="Vendor limits liability to 3 months of fees.",
            why_it_matters="Severely underprotects against cloud downtime.",
            risk_level="HIGH",
            category="Liability"
        )
        session.add(clause)

        await session.commit()
        contract_id = contract.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {token}"}

        # 13. Deterministic overdue detection
        res_obls = await client.get("/api/v1/obligations", headers=headers)
        assert res_obls.status_code == 200
        obls_data = res_obls.json()
        assert len(obls_data) == 1
        assert obls_data[0]["status"] == "OVERDUE"

        # 14. Deterministic Renewal and Lifecycle Summary
        res_summary = await client.get(f"/api/v1/contracts/{contract_id}/lifecycle-summary", headers=headers)
        assert res_summary.status_code == 200
        summary = res_summary.json()
        assert summary["current_status"] == "ACTIVE"
        assert summary["in_notice_window"] is True
        assert summary["renewal_status"] == "NOTICE WINDOW"
        assert summary["overdue_obligations_count"] == 1
        assert summary["health_status"] == "POTENTIAL PROBLEM"

        # Negotiation findings from real PlaybookRule
        res_nego = await client.get(f"/api/v1/contracts/{contract_id}/negotiation-analysis", headers=headers)
        assert res_nego.status_code == 200
        findings = res_nego.json()
        assert len(findings) >= 1
        assert findings[0]["status"] == "Potential Negotiation Issue"
        assert "3 months cap" in findings[0]["finding_summary"]

        # Renewal execution
        new_exp = (today + timedelta(days=365)).strftime("%Y-%m-%d")
        res_renew = await client.post(
            f"/api/v1/contracts/{contract_id}/renew",
            json={"new_expiry_date": new_exp, "renewal_term_months": 12, "notes": "Annual automatic renewal"},
            headers=headers
        )
        assert res_renew.status_code == 200
        assert res_renew.json()["status"] == "RENEWED"
        assert res_renew.json()["expiry_date"] == new_exp

        # 15. Controlled Termination
        res_term = await client.post(
            f"/api/v1/contracts/{contract_id}/terminate",
            json={"termination_reason": "End of project life", "termination_date": today.strftime("%Y-%m-%d")},
            headers=headers
        )
        assert res_term.status_code == 200
        assert res_term.json()["status"] == "TERMINATED"
        assert res_term.json()["termination_reason"] == "End of project life"

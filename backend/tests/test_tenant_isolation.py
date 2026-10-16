"""
Comprehensive test suite for Phase C: Strict Multi-Tenant Isolation.

Test Matrix:
1. User can access own organization contract
2. User cannot access foreign contract (404/403)
3. User cannot delete foreign contract
4. User cannot upload against foreign contract
5. User cannot access foreign contract clauses
6. User cannot access foreign risks
7. User cannot access foreign obligations
8. User cannot update foreign obligation
9. User cannot upload evidence to foreign obligation
10. User cannot access foreign audit logs
11. User cannot switch to unassociated organization (HTTP 403)
12. User can switch to an organization where they have active membership
13. After switching, old tenant data disappears from API results
14. X-Tenant-ID cannot bypass membership (HTTP 403 when trying to access foreign tenant)
15. Path traversal cannot escape tenant storage (ValueError / rejection)
16. No Northstar fallback remains: unauthenticated / unassociated user gets 401/403
"""

import io
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy.future import select

from app.main import app
from app.models.user import User, OrganizationMember
from app.models.organization import Organization
from app.models.contract import Contract, ContractClause, ContractRisk
from app.models.obligation import Obligation
from app.models.audit import AuditLog
from app.services.storage.local import storage_client
from app.core.security import get_password_hash, create_access_token


import uuid

async def _setup_two_tenants(test_engine):
    """
    Sets up two distinct organizations: Org Alpha and Org Beta,
    with contracts, obligations, clauses, risks, and audit logs.
    """
    suffix = uuid.uuid4().hex[:8]
    TestSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with TestSessionLocal() as session:
        # Org Alpha
        org_a = Organization(
            name=f"Alpha Corp {suffix}",
            slug=f"alpha-corp-{suffix}",
            account_type="BUSINESS",
        )
        session.add(org_a)

        # Org Beta
        org_b = Organization(
            name=f"Beta Corp {suffix}",
            slug=f"beta-corp-{suffix}",
            account_type="BUSINESS",
        )
        session.add(org_b)
        await session.flush()

        # User Alpha (Member of Org Alpha only)
        user_a = User(
            email=f"user_a_{suffix}@alpha.internal",
            password_hash=get_password_hash("Password123!"),
            full_name="Alpha User",
        )
        session.add(user_a)
        await session.flush()

        mem_a = OrganizationMember(
            organization_id=org_a.id,
            user_id=user_a.id,
            role="LEGAL_MANAGER",
            status="ACTIVE",
        )
        session.add(mem_a)

        # User Beta (Member of Org Beta only)
        user_b = User(
            email=f"user_b_{suffix}@beta.internal",
            password_hash=get_password_hash("Password123!"),
            full_name="Beta User",
        )
        session.add(user_b)
        await session.flush()

        mem_b = OrganizationMember(
            organization_id=org_b.id,
            user_id=user_b.id,
            role="LEGAL_MANAGER",
            status="ACTIVE",
        )
        session.add(mem_b)

        # User Dual (Member of both Org Alpha and Org Beta)
        user_dual = User(
            email=f"user_dual_{suffix}@contractly.internal",
            password_hash=get_password_hash("Password123!"),
            full_name="Dual Org User",
        )
        session.add(user_dual)
        await session.flush()

        mem_dual_a = OrganizationMember(
            organization_id=org_a.id,
            user_id=user_dual.id,
            role="LEGAL_MANAGER",
            status="ACTIVE",
        )
        mem_dual_b = OrganizationMember(
            organization_id=org_b.id,
            user_id=user_dual.id,
            role="LEGAL_REVIEWER",
            status="ACTIVE",
        )
        session.add(mem_dual_a)
        session.add(mem_dual_b)

        # Contract Alpha
        ctr_a = Contract(
            organization_id=org_a.id,
            contract_id="CTR-ALPHA-001",
            title="Alpha Agreement",
            contract_type="Master Services Agreement",
            counterparty="Alpha Vendor",
            department="Legal",
            value=100000.0,
            currency="INR",
            status="ACTIVE",
        )
        session.add(ctr_a)

        # Contract Beta
        ctr_b = Contract(
            organization_id=org_b.id,
            contract_id="CTR-BETA-001",
            title="Beta Agreement",
            contract_type="Master Services Agreement",
            counterparty="Beta Vendor",
            department="Legal",
            value=200000.0,
            currency="INR",
            status="ACTIVE",
        )
        session.add(ctr_b)
        await session.flush()

        # Clause Beta & Risk Beta
        clause_b = ContractClause(
            contract_id=ctr_b.id,
            clause_title="Beta Confidentiality",
            section_number="Section 9.1",
            original_text="Beta terms strictly private.",
            plain_language="Confidential to Beta.",
            why_it_matters="Protects Beta trade secrets.",
            risk_level="LOW",
            category="Confidentiality"
        )
        session.add(clause_b)

        risk_b = ContractRisk(
            contract_id=ctr_b.id,
            risk_title="Beta Financial Exposure",
            potential_impact="Unlimited indemnity under Beta clause 12",
            severity="HIGH",
            remedy_recommendation="Cap liability"
        )
        session.add(risk_b)

        # Obligation Beta
        obl_b = Obligation(
            contract_id=ctr_b.id,
            obligor_party="Beta Corp",
            obligee_party="Beta Vendor",
            title="Beta Delivery SLA",
            description="Deliver weekly report",
            due_date="2027-06-01",
            status="UPCOMING"
        )
        session.add(obl_b)

        # AuditLog Beta
        audit_b = AuditLog(
            organization_id=org_b.id,
            user_email="user_b@beta.internal",
            action="CONTRACT_INITIALIZED",
            object_type="CONTRACT",
            object_id=ctr_b.id,
            detail="Contract Beta created in Org Beta"
        )
        session.add(audit_b)

        await session.commit()

        token_a = create_access_token(subject=user_a.id, org_id=org_a.id, role="LEGAL_MANAGER")
        token_b = create_access_token(subject=user_b.id, org_id=org_b.id, role="LEGAL_MANAGER")
        token_dual = create_access_token(subject=user_dual.id, org_id=org_a.id, role="LEGAL_MANAGER")

        return {
            "org_a": org_a,
            "org_b": org_b,
            "user_a": user_a,
            "user_b": user_b,
            "user_dual": user_dual,
            "ctr_a": ctr_a,
            "ctr_b": ctr_b,
            "clause_b": clause_b,
            "risk_b": risk_b,
            "obl_b": obl_b,
            "audit_b": audit_b,
            "token_a": token_a,
            "token_b": token_b,
            "token_dual": token_dual,
        }


@pytest.mark.asyncio
async def test_user_can_access_own_contract_and_not_foreign_contract(test_engine):
    """1 & 2. User can access own organization contract, cannot access foreign contract."""
    data = await _setup_two_tenants(test_engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers_a = {"Authorization": f"Bearer {data['token_a']}"}
        # 1. Access own contract -> 200
        res_own = await ac.get(f"/api/v1/contracts/{data['ctr_a'].id}", headers=headers_a)
        assert res_own.status_code == 200
        assert res_own.json()["id"] == data["ctr_a"].id

        # 2. Access foreign contract -> 404 (Not found in tenant)
        res_foreign = await ac.get(f"/api/v1/contracts/{data['ctr_b'].id}", headers=headers_a)
        assert res_foreign.status_code == 404


@pytest.mark.asyncio
async def test_user_cannot_delete_foreign_contract(test_engine):
    """3. User cannot delete foreign contract."""
    data = await _setup_two_tenants(test_engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers_a = {"Authorization": f"Bearer {data['token_a']}"}
        res_del = await ac.delete(f"/api/v1/contracts/{data['ctr_b'].id}", headers=headers_a)
        assert res_del.status_code == 404


@pytest.mark.asyncio
async def test_user_cannot_create_obligation_on_foreign_contract(test_engine):
    """4. User cannot upload/create obligations against foreign contract."""
    data = await _setup_two_tenants(test_engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers_a = {"Authorization": f"Bearer {data['token_a']}"}
        res = await ac.post(
            f"/api/v1/contracts/{data['ctr_b'].id}/obligations",
            json={
                "title": "Unauthorized Obligation",
                "obligor_party": "Org Alpha",
                "obligee_party": "Vendor Beta",
                "description": "Attempted foreign creation",
                "due_date": "2027-01-01"
            },
            headers=headers_a
        )
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_user_cannot_access_foreign_clause_or_risk(test_engine):
    """5 & 6. User cannot access foreign contract clauses or risks."""
    data = await _setup_two_tenants(test_engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers_a = {"Authorization": f"Bearer {data['token_a']}"}
        # Foreign clause
        res_clause = await ac.get(f"/api/v1/contracts/clauses/{data['clause_b'].id}", headers=headers_a)
        assert res_clause.status_code == 404

        # Foreign risk
        res_risk = await ac.get(f"/api/v1/contracts/risks/{data['risk_b'].id}", headers=headers_a)
        assert res_risk.status_code == 404


@pytest.mark.asyncio
async def test_user_cannot_access_foreign_obligations(test_engine):
    """7, 8, 9. User cannot access, update status, or upload evidence to foreign obligation."""
    data = await _setup_two_tenants(test_engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers_a = {"Authorization": f"Bearer {data['token_a']}"}

        # 7. Foreign obligation list
        res_list = await ac.get(f"/api/v1/contracts/{data['ctr_b'].id}/obligations", headers=headers_a)
        assert res_list.status_code == 404

        # 8. Foreign obligation status update
        res_update = await ac.patch(
            f"/api/v1/obligations/{data['obl_b'].id}/status",
            json={"status": "FULFILLED"},
            headers=headers_a
        )
        assert res_update.status_code == 404

        # 9. Foreign obligation evidence upload
        file_content = b"Fake evidence"
        files = {"file": ("evidence.pdf", io.BytesIO(file_content), "application/pdf")}
        res_evidence = await ac.post(
            f"/api/v1/obligations/{data['obl_b'].id}/evidence",
            files=files,
            headers=headers_a
        )
        assert res_evidence.status_code == 404


@pytest.mark.asyncio
async def test_user_cannot_access_foreign_audit_logs(test_engine):
    """10. User cannot query foreign organization audit logs."""
    data = await _setup_two_tenants(test_engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers_a = {"Authorization": f"Bearer {data['token_a']}"}
        res = await ac.get("/api/v1/organizations/audit-logs", headers=headers_a)
        assert res.status_code == 200
        logs = res.json()
        # Verify no logs belonging to Org Beta appear in Org Alpha's audit logs
        for log in logs:
            assert log["organization_id"] == data["org_a"].id
            assert log["object_id"] != data["ctr_b"].id


@pytest.mark.asyncio
async def test_user_cannot_switch_to_unassociated_organization(test_engine):
    """11. User cannot switch to an organization where they lack active membership (HTTP 403)."""
    data = await _setup_two_tenants(test_engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # User A only has membership in Org A, tries switching to Org B
        headers_a = {"Authorization": f"Bearer {data['token_a']}"}
        res = await ac.post(
            "/api/v1/auth/switch-tenant",
            json={"organization_id": data["org_b"].id},
            headers=headers_a
        )
        assert res.status_code == 403
        assert "Not an active member" in res.json()["detail"]


@pytest.mark.asyncio
async def test_user_can_switch_tenant_and_data_refreshes(test_engine):
    """12 & 13. User with membership in multiple orgs can switch tenant, and old tenant data disappears."""
    data = await _setup_two_tenants(test_engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # User Dual starts scoped to Org Alpha
        headers_dual = {"Authorization": f"Bearer {data['token_dual']}"}

        # 1. In Org Alpha, can see Contract Alpha, but not Contract Beta
        list_initial = await ac.get("/api/v1/contracts", headers=headers_dual)
        assert list_initial.status_code == 200
        ctr_ids = [c["id"] for c in list_initial.json()]
        assert data["ctr_a"].id in ctr_ids
        assert data["ctr_b"].id not in ctr_ids

        # 2. Switch to Org Beta
        res_switch = await ac.post(
            "/api/v1/auth/switch-tenant",
            json={"organization_id": data["org_b"].id},
            headers=headers_dual
        )
        assert res_switch.status_code == 200
        new_token = res_switch.json()["access_token"]
        assert res_switch.json()["user"]["organization_id"] == data["org_b"].id
        assert res_switch.json()["user"]["role"] == "LEGAL_REVIEWER"

        # 3. Request with newly scoped token: Old tenant (Alpha) contracts disappear! Beta appears!
        headers_switched = {"Authorization": f"Bearer {new_token}"}
        list_switched = await ac.get("/api/v1/contracts", headers=headers_switched)
        assert list_switched.status_code == 200
        switched_ctr_ids = [c["id"] for c in list_switched.json()]
        assert data["ctr_b"].id in switched_ctr_ids
        assert data["ctr_a"].id not in switched_ctr_ids


@pytest.mark.asyncio
async def test_x_tenant_id_cannot_bypass_membership(test_engine):
    """14. Attacker sending X-Tenant-ID header cannot bypass membership check (HTTP 403)."""
    data = await _setup_two_tenants(test_engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers_attack = {
            "Authorization": f"Bearer {data['token_a']}",
            "X-Tenant-ID": data["org_b"].id  # User A claims to be Org B via header
        }
        res = await ac.get("/api/v1/contracts", headers=headers_attack)
        assert res.status_code == 403
        assert f"Not an active member of organization '{data['org_b'].id}'" in res.json()["detail"]


def test_path_traversal_cannot_escape_tenant_storage():
    """15. Storage service rejects directory traversal attempts."""
    # Attempting to traverse outside base storage directory
    with pytest.raises(ValueError, match="directory traversal prohibited"):
        storage_client._resolve_path("../../etc/passwd")

    # Attempting to escape tenant folder
    with pytest.raises(ValueError, match="Cross-tenant storage access prohibited"):
        storage_client._resolve_path("tenant_a/../tenant_b/contract.pdf", expected_tenant_id="tenant_a")


@pytest.mark.asyncio
async def test_no_northstar_fallback_for_unauthenticated_request():
    """16. Request without valid auth receives 401, never default Northstar tenant."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/contracts")
        assert res.status_code == 401

import pytest
import io
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from app.main import app
from app.core.security import get_password_hash, create_access_token
from app.models.organization import Organization
from app.models.user import User, OrganizationMember
from app.models.contract import Contract, ContractApprovalStep
from app.models.vendor import Vendor
from app.models.playbook import PlaybookRule
from app.models.audit import AuditLog

@pytest.mark.asyncio
async def test_empty_database_returns_empty_lists_no_mocks(test_engine):
    """
    Verifies that an empty database returns empty arrays for all business entities,
    with zero fabricated or mock records.
    """
    suffix = uuid.uuid4().hex[:8]
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        org = Organization(name=f"Empty Test Org {suffix}", slug=f"empty-test-org-{suffix}")
        session.add(org)
        await session.flush()

        user = User(
            email=f"empty_{suffix}@example.com",
            password_hash=get_password_hash("SecretPassword123!"),
            full_name="Empty Test User"
        )
        session.add(user)
        await session.flush()

        member = OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role="OWNER"
        )
        session.add(member)
        await session.commit()

        token = create_access_token(subject=user.id, org_id=org.id, role="OWNER")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {token}"}

        res = await client.get("/api/v1/contracts", headers=headers)
        assert res.status_code == 200
        assert res.json() == []

        res = await client.get("/api/v1/obligations", headers=headers)
        assert res.status_code == 200
        assert res.json() == []

        res = await client.get("/api/v1/vendors", headers=headers)
        assert res.status_code == 200
        assert res.json() == []

        res = await client.get("/api/v1/playbook", headers=headers)
        assert res.status_code == 200
        assert res.json() == []

        res = await client.get("/api/v1/organizations/audit-logs", headers=headers)
        assert res.status_code == 200
        assert res.json() == []

@pytest.mark.asyncio
async def test_vendors_crud_and_tenant_isolation(test_engine):
    """
    Verifies that vendors are strictly isolated to the authenticated tenant organization.
    Tenant A vendors must never be visible to Tenant B.
    """
    suffix = uuid.uuid4().hex[:8]
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        org_a = Organization(name=f"Vendor Org A {suffix}", slug=f"vendor-org-a-{suffix}")
        org_b = Organization(name=f"Vendor Org B {suffix}", slug=f"vendor-org-b-{suffix}")
        session.add_all([org_a, org_b])
        await session.flush()

        user_a = User(email=f"vendor_a_{suffix}@test.com", password_hash=get_password_hash("Password123!"), full_name="User A")
        user_b = User(email=f"vendor_b_{suffix}@test.com", password_hash=get_password_hash("Password123!"), full_name="User B")
        session.add_all([user_a, user_b])
        await session.flush()

        member_a = OrganizationMember(organization_id=org_a.id, user_id=user_a.id, role="OWNER")
        member_b = OrganizationMember(organization_id=org_b.id, user_id=user_b.id, role="OWNER")
        session.add_all([member_a, member_b])
        await session.commit()

        org_a_id = org_a.id
        token_a = create_access_token(subject=user_a.id, org_id=org_a.id, role="OWNER")
        token_b = create_access_token(subject=user_b.id, org_id=org_b.id, role="OWNER")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client_a:
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # Create vendor in Org A
        create_res = await client_a.post("/api/v1/vendors", headers=headers_a, json={
            "name": "Acme Supplier Inc.",
            "contact_email": "procurement@acme.com",
            "contract_count": 1,
            "total_contract_value": 500000.0,
            "risk_rating": "LOW"
        })
        assert create_res.status_code == 201
        vendor_data = create_res.json()
        vendor_id = vendor_data["id"]
        assert vendor_data["name"] == "Acme Supplier Inc."
        assert vendor_data["organization_id"] == org_a_id

        # Verify Org A sees it
        list_a = await client_a.get("/api/v1/vendors", headers=headers_a)
        assert list_a.status_code == 200
        assert len(list_a.json()) == 1
        assert list_a.json()[0]["id"] == vendor_id

    # Verify Org B cannot see Org A's vendor
    async with AsyncClient(transport=transport, base_url="http://test") as client_b:
        headers_b = {"Authorization": f"Bearer {token_b}"}

        list_b = await client_b.get("/api/v1/vendors", headers=headers_b)
        assert list_b.status_code == 200
        assert list_b.json() == []

        get_foreign = await client_b.get(f"/api/v1/vendors/{vendor_id}", headers=headers_b)
        assert get_foreign.status_code == 404

@pytest.mark.asyncio
async def test_playbook_rules_tenant_isolation(test_engine):
    """
    Verifies that playbook rules are stored in the database and scoped to the active tenant.
    """
    suffix = uuid.uuid4().hex[:8]
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        org_a = Organization(name=f"Playbook Org A {suffix}", slug=f"playbook-org-a-{suffix}")
        org_b = Organization(name=f"Playbook Org B {suffix}", slug=f"playbook-org-b-{suffix}")
        session.add_all([org_a, org_b])
        await session.flush()

        user_a = User(email=f"pb_a_{suffix}@test.com", password_hash=get_password_hash("Password123!"), full_name="PB User A")
        user_b = User(email=f"pb_b_{suffix}@test.com", password_hash=get_password_hash("Password123!"), full_name="PB User B")
        session.add_all([user_a, user_b])
        await session.flush()

        member_a = OrganizationMember(organization_id=org_a.id, user_id=user_a.id, role="LEGAL_MANAGER")
        member_b = OrganizationMember(organization_id=org_b.id, user_id=user_b.id, role="LEGAL_MANAGER")
        session.add_all([member_a, member_b])
        await session.commit()

        token_a = create_access_token(subject=user_a.id, org_id=org_a.id, role="LEGAL_MANAGER")
        token_b = create_access_token(subject=user_b.id, org_id=org_b.id, role="LEGAL_MANAGER")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client_a:
        headers_a = {"Authorization": f"Bearer {token_a}"}

        create_res = await client_a.post("/api/v1/playbook", headers=headers_a, json={
            "category": "Limitation of Liability",
            "preferred_standard": "Liability shall be capped at 12 months fees.",
            "fallback_acceptable": "Liability shall be capped at 24 months fees.",
            "prohibited_terms": ["unlimited liability", "waiver of gross negligence"],
            "negotiation_guidance": "Never accept uncapped damages."
        })
        assert create_res.status_code == 201
        rule_id = create_res.json()["id"]

        rules_a = await client_a.get("/api/v1/playbook", headers=headers_a)
        assert rules_a.status_code == 200
        assert len(rules_a.json()) == 1

    async with AsyncClient(transport=transport, base_url="http://test") as client_b:
        headers_b = {"Authorization": f"Bearer {token_b}"}

        rules_b = await client_b.get("/api/v1/playbook", headers=headers_b)
        assert rules_b.status_code == 200
        assert rules_b.json() == []

        foreign_rule = await client_b.get(f"/api/v1/playbook/{rule_id}", headers=headers_b)
        assert foreign_rule.status_code == 404

@pytest.mark.asyncio
async def test_contract_approvals_database_backed(test_engine):
    """
    Verifies that contract approval steps are persisted in the database,
    decision submission updates step and contract state, and writes to real audit logs.
    """
    suffix = uuid.uuid4().hex[:8]
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        org = Organization(name=f"Approval Org {suffix}", slug=f"approval-org-{suffix}")
        session.add(org)
        await session.flush()

        user = User(email=f"approver_{suffix}@test.com", password_hash=get_password_hash("Password123!"), full_name="Alice Approver")
        session.add(user)
        await session.flush()

        member = OrganizationMember(organization_id=org.id, user_id=user.id, role="LEGAL_MANAGER")
        session.add(member)
        await session.commit()

        token = create_access_token(subject=user.id, org_id=org.id, role="LEGAL_MANAGER")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {token}"}

        # Upload contract
        sample_doc = b"Master Services Agreement between Alice and Bob. Section 1: Standard terms."
        files = {"file": ("test_agreement.txt", io.BytesIO(sample_doc), "text/plain")}
        data = {
            "title": "Vendor Services Agreement",
            "contract_type": "Master Services Agreement",
            "counterparty": "Bob Enterprises",
            "department": "Procurement",
            "value": 150000.0,
            "currency": "INR"
        }
        upload_res = await client.post("/api/v1/contracts/upload", headers=headers, files=files, data=data)
        assert upload_res.status_code == 200
        contract_data = upload_res.json()
        contract_id = contract_data["id"]
        steps = contract_data["approval_steps"]
        assert len(steps) >= 2
        step1 = steps[0]
        assert step1["decision"] == "PENDING"

        # Submit decision on step 1
        decision_res = await client.post(
            f"/api/v1/contracts/{contract_id}/approvals/{step1['id']}/decision",
            headers=headers,
            json={"decision": "APPROVED", "comments": "Budget validated and reviewed."}
        )
        assert decision_res.status_code == 200
        updated_step = decision_res.json()
        assert updated_step["decision"] == "APPROVED"
        assert updated_step["comments"] == "Budget validated and reviewed."

        # Verify audit logs have recorded this real action
        audit_res = await client.get("/api/v1/organizations/audit-logs", headers=headers)
        assert audit_res.status_code == 200
        audit_entries = audit_res.json()
        assert any(e["action"] == "APPROVAL_DECISION_SUBMITTED" for e in audit_entries)
        assert any(e["action"] == "CONTRACT_UPLOADED" for e in audit_entries)

"""
Contractly Data Management, Demo Reset, and Customer Handover Test Suite.
Phase 7 Verification:
- An organization administrator can manage and export eligible data in their own organization.
- An organization administrator cannot access or delete another organization's records.
- Platform administrator permissions match documented role policy.
- Demo reset strictly affects the designated demo organization ('northstar-tech').
- Demo reset preserves live advocate profiles and customer matters.
- Database records and stored documents are cleaned up consistently via StorageClient.
- Legal holds and retention rules prevent unauthorized data purging.
- Non-conforming confirmation tokens ('CLEAR WORKSPACE', 'RESET DEMO') are rejected.
- Audit events record operations without exposing private contract contents.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy.future import select

from app.main import app
from app.models.user import User, OrganizationMember
from app.models.organization import Organization, Department
from app.models.contract import Contract, ContractVersion, ContractClause, ContractRisk
from app.models.obligation import Obligation, ObligationEvidence
from app.models.audit import AuditLog
from app.models.lawyer import LawyerProfile, LegalMatter, LawyerVerificationStatus
from app.core.security import get_password_hash, create_access_token
from app.services.storage import storage_client


@pytest.mark.asyncio
async def test_org_admin_summary_and_export(test_engine):
    """1. Org admin can view summary metrics and export eligible workspace data."""
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as db:
        # Create organization
        org = Organization(
            name="Acme Legal Corp",
            slug="acme-legal-corp",
            account_type="BUSINESS"
        )
        db.add(org)
        await db.flush()

        # Create admin user
        user = User(
            email="admin@acmelegal.test",
            password_hash=get_password_hash("Secret123!"),
            full_name="Acme Admin",
            is_active=True
        )
        db.add(user)
        await db.flush()

        member = OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role="OWNER"
        )
        db.add(member)

        # Create contract
        c = Contract(
            organization_id=org.id,
            contract_id="CTR-ACME-001",
            title="Acme Master Agreement",
            contract_type="Master Services Agreement",
            counterparty="Acme Partner Inc.",
            status="ACTIVE",
            risk_level="LOW"
        )
        db.add(c)
        await db.flush()

        # Contract version with mock storage file
        storage_rel_path = f"{org.id}/contracts/acme_v1.pdf"
        storage_client.save_file(storage_rel_path, b"%PDF-1.4 Mock Acme Content", tenant_id=org.id)
        v = ContractVersion(
            contract_id=c.id,
            version_number="v1.0",
            filename="acme_v1.pdf",
            file_storage_path=storage_rel_path,
            file_mime_type="application/pdf",
            file_byte_size=1024,
            sha256_checksum="0" * 64
        )
        db.add(v)

        # Obligation
        ob = Obligation(
            contract_id=c.id,
            obligor_party="Acme",
            obligee_party="Partner",
            title="Quarterly Review",
            description="Review service performance quarterly."
        )
        db.add(ob)
        await db.commit()

        org_id = org.id
        user_id = user.id

    token = create_access_token(subject=user_id, org_id=org_id, role="OWNER")
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # GET summary
        summary_res = await ac.get("/api/v1/organizations/data-management/summary", headers=headers)
        assert summary_res.status_code == 200
        data = summary_res.json()
        assert data["organization_slug"] == "acme-legal-corp"
        assert data["legal_hold_count"] == 0
        assert data["can_clear_workspace"] is True
        assert data["storage_files_count"] >= 1

        # GET export
        export_res = await ac.get("/api/v1/organizations/data-management/export", headers=headers)
        assert export_res.status_code == 200
        export_data = export_res.json()
        assert "contracts" in export_data
        assert len(export_data["contracts"]) == 1
        assert export_data["contracts"][0]["title"] == "Acme Master Agreement"
        assert "obligations" in export_data
        assert len(export_data["obligations"]) == 1


@pytest.mark.asyncio
async def test_legal_hold_blocks_workspace_clearing(test_engine):
    """2. Active legal hold prevents clearing workspace data with HTTP 409."""
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as db:
        org = Organization(name="Hold Test Org", slug="hold-test-org", account_type="BUSINESS")
        db.add(org)
        await db.flush()

        user = User(email="owner@holdtest.test", password_hash=get_password_hash("Secret123!"), full_name="Hold Test Owner", is_active=True)
        db.add(user)
        await db.flush()

        member = OrganizationMember(organization_id=org.id, user_id=user.id, role="OWNER")
        db.add(member)

        # Contract under legal hold
        c = Contract(
            organization_id=org.id,
            contract_id="CTR-HOLD-001",
            title="Litigated Agreement",
            contract_type="Master Services Agreement",
            counterparty="Litigant Counterparty Inc.",
            status="LEGAL_HOLD",
            tags="LEGAL_HOLD, Dispute"
        )
        db.add(c)
        await db.commit()

        org_id = org.id
        user_id = user.id

    token = create_access_token(subject=user_id, org_id=org_id, role="OWNER")
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Check summary shows hold
        sum_res = await ac.get("/api/v1/organizations/data-management/summary", headers=headers)
        assert sum_res.status_code == 200
        assert sum_res.json()["legal_hold_count"] == 1
        assert sum_res.json()["can_clear_workspace"] is False

        # Attempt to clear workspace
        clear_res = await ac.post(
            "/api/v1/organizations/data-management/clear-workspace",
            headers=headers,
            json={"confirmation": "CLEAR WORKSPACE"}
        )
        assert clear_res.status_code == 409
        assert "legal hold" in clear_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_org_admin_clear_workspace_success(test_engine):
    """3. Clear workspace succeeds when confirmed, deleting business records & files, preserving account."""
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as db:
        org = Organization(name="Purge Corp", slug="purge-corp", account_type="BUSINESS")
        db.add(org)
        await db.flush()

        dept = Department(organization_id=org.id, name="Legal")
        db.add(dept)

        user = User(email="owner@purgecorp.test", password_hash=get_password_hash("Secret123!"), full_name="Purge Corp Owner", is_active=True)
        db.add(user)
        await db.flush()

        member = OrganizationMember(organization_id=org.id, user_id=user.id, role="OWNER")
        db.add(member)

        c = Contract(
            organization_id=org.id,
            contract_id="CTR-PURGE-01",
            title="Dispensable Agreement",
            contract_type="Master Services Agreement",
            counterparty="Dispensable Partner Inc.",
            status="ACTIVE"
        )
        db.add(c)
        await db.flush()

        # Save physical file to storage
        storage_rel_path = f"{org.id}/contracts/purge_file.pdf"
        storage_client.save_file(storage_rel_path, b"purge-me", tenant_id=org.id)
        v = ContractVersion(
            contract_id=c.id,
            version_number="v1.0",
            filename="purge_file.pdf",
            file_storage_path=storage_rel_path,
            file_mime_type="application/pdf",
            file_byte_size=1024,
            sha256_checksum="0" * 64
        )
        db.add(v)
        await db.commit()

        org_id = org.id
        user_id = user.id

    # Verify file exists before clearing
    assert storage_client.file_exists(storage_rel_path, tenant_id=org_id) is True

    token = create_access_token(subject=user_id, org_id=org_id, role="OWNER")
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Invalid confirmation rejected
        bad_conf = await ac.post(
            "/api/v1/organizations/data-management/clear-workspace",
            headers=headers,
            json={"confirmation": "INVALID"}
        )
        assert bad_conf.status_code == 400

        # Valid confirmation
        clear_res = await ac.post(
            "/api/v1/organizations/data-management/clear-workspace",
            headers=headers,
            json={"confirmation": "CLEAR WORKSPACE"}
        )
        assert clear_res.status_code == 200
        data = clear_res.json()
        assert data["status"] == "SUCCESS"
        assert data["contracts_deleted"] == 1

    # Verify DB state: contract deleted, file deleted, user & org intact
    async with async_session() as db:
        c_check = await db.execute(select(Contract).where(Contract.organization_id == org_id))
        assert len(c_check.scalars().all()) == 0

        # Organization & user still exist
        org_check = await db.execute(select(Organization).where(Organization.id == org_id))
        assert org_check.scalar_one_or_none() is not None

        user_check = await db.execute(select(User).where(User.id == user_id))
        assert user_check.scalar_one_or_none() is not None

        # Audit log was created
        audit_res = await db.execute(
            select(AuditLog).where(AuditLog.organization_id == org_id, AuditLog.action == "WORKSPACE_DATA_CLEARED")
        )
        assert audit_res.scalar_one_or_none() is not None

    # Storage file was removed
    assert storage_client.file_exists(storage_rel_path, tenant_id=org_id) is False


@pytest.mark.asyncio
async def test_demo_reset_preview_and_execution(test_engine):
    """4. Platform super admin can preview and reset the designated demo workspace ('northstar-tech')."""
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as db:
        # Ensure northstar-tech demo org exists
        res = await db.execute(select(Organization).where(Organization.slug == "northstar-tech"))
        demo_org = res.scalar_one_or_none()
        if not demo_org:
            demo_org = Organization(name="Northstar Technologies Pvt. Ltd.", slug="northstar-tech", account_type="BUSINESS")
            db.add(demo_org)
            await db.flush()

        # Platform super admin
        admin = User(
            email="platform_data_admin@contractly.test",
            password_hash=get_password_hash("Secret123!"),
            full_name="Platform Data Admin",
            is_active=True,
            is_super_admin=True
        )
        db.add(admin)

        # Seed illustrative contract
        demo_c = Contract(
            organization_id=demo_org.id,
            contract_id="CTR-DEMO-TEMP",
            title="Temporary Illustrative Demo",
            contract_type="Master Services Agreement",
            counterparty="Illustrative Demo Counterparty",
            status="ACTIVE"
        )
        db.add(demo_c)
        await db.commit()

        admin_id = admin.id

    admin_token = create_access_token(subject=admin_id)
    headers = {"Authorization": f"Bearer {admin_token}"}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Preview demo reset
        preview_res = await ac.get("/api/v1/platform/data-management/demo-workspace/preview", headers=headers)
        assert preview_res.status_code == 200
        prev_data = preview_res.json()
        assert prev_data["demo_org_found"] is True
        assert prev_data["organization_slug"] == "northstar-tech"
        assert prev_data["required_confirmation"] == "RESET DEMO"

        # Execute demo reset with reseed
        reset_res = await ac.post(
            "/api/v1/platform/data-management/demo-workspace/reset",
            headers=headers,
            json={"confirmation": "RESET DEMO", "reseed": True}
        )
        assert reset_res.status_code == 200
        res_data = reset_res.json()
        assert res_data["status"] == "SUCCESS"
        assert res_data["reseeded"] is True
        assert res_data["reseeded_contracts_count"] == 2

    # Verify deterministic demo contracts reseeded
    async with async_session() as db:
        c_check = await db.execute(select(Contract).where(Contract.organization_id == demo_org.id))
        contracts = c_check.scalars().all()
        titles = {c.title for c in contracts}
        assert "Vendor Master Services Agreement" in titles
        assert "Senior Engineering Leadership Employment Agreement" in titles

        # Verify audit logs
        audit_res = await db.execute(
            select(AuditLog).where(AuditLog.organization_id == demo_org.id, AuditLog.action == "DEMO_WORKSPACE_RESET_COMPLETED")
        )
        assert audit_res.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_demo_reset_does_not_affect_real_advocates_or_matters(test_engine):
    """5. Demo reset preserves registered advocate profiles and live legal matters."""
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as db:
        # Create genuine customer organization
        client_org = Organization(name="Live Enterprise Client", slug="live-enterprise-client", account_type="BUSINESS")
        db.add(client_org)
        await db.flush()

        # Create genuine lawyer organization and advocate profile
        lawyer_org = Organization(name="Elite Chambers", slug="elite-chambers", account_type="LEGAL_PROFESSIONAL")
        db.add(lawyer_org)
        await db.flush()

        lawyer_user = User(email="advocate.live@elite.test", password_hash=get_password_hash("Secret123!"), full_name="Senior Advocate Sharma", is_active=True)
        db.add(lawyer_user)
        await db.flush()

        advocate = LawyerProfile(
            user_id=lawyer_user.id,
            organization_id=lawyer_org.id,
            bar_council_number="D/9999/2015",
            state_bar_council="Bar Council of Delhi",
            admitted_jurisdictions="Delhi High Court, Supreme Court of India",
            verification_status=LawyerVerificationStatus.VERIFIED.value
        )
        db.add(advocate)
        await db.flush()

        # Create live legal matter
        matter = LegalMatter(
            matter_code="MAT-LIVE-001",
            title="Cross-Border Joint Venture Agreement Review",
            matter_type="COMMERCIAL_CONTRACT",
            counterparty_name="Live Joint Venture Counterparty",
            client_organization_id=client_org.id,
            lawyer_organization_id=lawyer_org.id,
            status="MATTER_ACTIVE"
        )
        db.add(matter)

        # Super admin
        admin = User(email="superadmin_isolation@contractly.test", password_hash=get_password_hash("Secret123!"), full_name="Super Admin Isolation", is_super_admin=True, is_active=True)
        db.add(admin)
        await db.commit()

        advocate_id = advocate.id
        matter_id = matter.id
        admin_id = admin.id

    admin_token = create_access_token(subject=admin_id)
    headers = {"Authorization": f"Bearer {admin_token}"}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Execute demo reset
        reset_res = await ac.post(
            "/api/v1/platform/data-management/demo-workspace/reset",
            headers=headers,
            json={"confirmation": "RESET DEMO", "reseed": False}
        )
        assert reset_res.status_code == 200

    # Verify live advocate and matter are 100% intact
    async with async_session() as db:
        adv_check = await db.execute(select(LawyerProfile).where(LawyerProfile.id == advocate_id))
        assert adv_check.scalar_one_or_none() is not None

        mat_check = await db.execute(select(LegalMatter).where(LegalMatter.id == matter_id))
        assert mat_check.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_single_contract_deletion_with_storage_cleanup_and_legal_hold(test_engine):
    """6. Single contract DELETE /contracts/{id} checks legal hold and cleans up storage."""
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as db:
        org = Organization(name="Single Delete Org", slug="single-delete-org", account_type="BUSINESS")
        db.add(org)
        await db.flush()

        user = User(email="owner@singledelete.test", password_hash=get_password_hash("Secret123!"), full_name="Single Delete Owner", is_active=True)
        db.add(user)
        await db.flush()

        member = OrganizationMember(organization_id=org.id, user_id=user.id, role="OWNER")
        db.add(member)

        # Normal contract with file
        c1 = Contract(
            organization_id=org.id,
            contract_id="CTR-DEL-01",
            title="Deletable NDA",
            contract_type="Non-Disclosure Agreement",
            counterparty="NDA Counterparty LLC",
            status="ACTIVE"
        )
        db.add(c1)
        await db.flush()

        storage_rel_path = f"{org.id}/contracts/c1_file.pdf"
        storage_client.save_file(storage_rel_path, b"test-c1-bytes", tenant_id=org.id)
        v1 = ContractVersion(
            contract_id=c1.id,
            version_number="v1.0",
            filename="c1_file.pdf",
            file_storage_path=storage_rel_path,
            file_mime_type="application/pdf",
            file_byte_size=1024,
            sha256_checksum="0" * 64
        )
        db.add(v1)

        # Contract with legal hold
        c_held = Contract(
            organization_id=org.id,
            contract_id="CTR-DEL-HELD",
            title="Litigated Contract",
            contract_type="Master Services Agreement",
            counterparty="Dispute Counterparty Inc.",
            status="LEGAL_HOLD"
        )
        db.add(c_held)
        await db.commit()

        c1_id = c1.id
        c_held_id = c_held.id
        org_id = org.id
        user_id = user.id

    token = create_access_token(subject=user_id, org_id=org_id, role="OWNER")
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Attempt to delete held contract -> 400 Bad Request
        res_held = await ac.delete(f"/api/v1/contracts/{c_held_id}", headers=headers)
        assert res_held.status_code == 400
        assert "legal hold" in res_held.json()["detail"].lower()

        # Delete normal contract -> 200 OK
        res_del = await ac.delete(f"/api/v1/contracts/{c1_id}", headers=headers)
        assert res_del.status_code == 200
        assert "deleted successfully" in res_del.json()["message"]

    # Verify physical file deleted
    assert storage_client.file_exists(storage_rel_path, tenant_id=org_id) is False

    # Verify audit log created
    async with async_session() as db:
        audit_res = await db.execute(
            select(AuditLog).where(AuditLog.organization_id == org_id, AuditLog.action == "CONTRACT_DELETED")
        )
        assert audit_res.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_customer_handover_checklist_endpoint(test_engine):
    """7. GET /platform/data-management/customer-handover-checklist returns onboarding checklist."""
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as db:
        admin = User(email="handover_admin@contractly.test", password_hash=get_password_hash("Secret123!"), full_name="Handover Admin", is_super_admin=True, is_active=True)
        db.add(admin)
        await db.commit()
        admin_id = admin.id

    admin_token = create_access_token(subject=admin_id)
    headers = {"Authorization": f"Bearer {admin_token}"}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/platform/data-management/customer-handover-checklist", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "checklist" in data
        assert len(data["checklist"]) >= 5
        categories = {item["category"] for item in data["checklist"]}
        assert "Tenant Isolation" in categories
        assert "Storage Integrity" in categories
        assert "Security" in categories


@pytest.mark.asyncio
async def test_cross_tenant_isolation_prevents_unauthorized_deletion(test_engine):
    """8. Tenant A administrator cannot view summary or clear Tenant B's workspace data."""
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as db:
        # Tenant A
        org_a = Organization(name="Tenant Alpha", slug="tenant-alpha", account_type="BUSINESS")
        db.add(org_a)
        await db.flush()
        user_a = User(email="admin.alpha@contractly.test", password_hash=get_password_hash("Secret123!"), full_name="Admin Alpha", is_active=True)
        db.add(user_a)
        await db.flush()
        member_a = OrganizationMember(organization_id=org_a.id, user_id=user_a.id, role="OWNER")
        db.add(member_a)

        # Tenant B
        org_b = Organization(name="Tenant Beta", slug="tenant-beta", account_type="BUSINESS")
        db.add(org_b)
        await db.flush()
        contract_b = Contract(
            organization_id=org_b.id,
            contract_id="CTR-BETA-001",
            title="Beta Confidential MSA",
            contract_type="Master Services Agreement",
            counterparty="Beta Counterparty Inc.",
            status="ACTIVE"
        )
        db.add(contract_b)
        await db.commit()

        user_a_id = user_a.id
        org_a_id = org_a.id
        org_b_id = org_b.id
        contract_b_id = contract_b.id

    # User A has token for Tenant A
    token_a = create_access_token(subject=user_a_id, org_id=org_a_id, role="OWNER")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # User A summary only shows Tenant A (0 contracts), not Tenant B's contract
        sum_res = await ac.get("/api/v1/organizations/data-management/summary", headers=headers_a)
        assert sum_res.status_code == 200
        assert sum_res.json()["organization_slug"] == "tenant-alpha"
        assert sum_res.json()["total_records"] == 0

        # User A attempts to delete Tenant B's contract -> 404 (not in Tenant A)
        del_res = await ac.delete(f"/api/v1/contracts/{contract_b_id}", headers=headers_a)
        assert del_res.status_code == 404

        # User A passes X-Tenant-ID header for Tenant B -> 403 Forbidden
        spoof_res = await ac.get(
            "/api/v1/organizations/data-management/summary",
            headers={**headers_a, "X-Tenant-ID": org_b_id}
        )
        assert spoof_res.status_code == 403

    # Tenant B's contract is completely intact
    async with async_session() as db:
        c_check = await db.execute(select(Contract).where(Contract.id == contract_b_id))
        assert c_check.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_unauthorized_and_unauthenticated_requests_rejected(test_engine):
    """9. Non-super-admin gets 403 on demo reset; unauthenticated caller gets 401."""
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as db:
        regular_org = Organization(name="Regular Org", slug="regular-org", account_type="BUSINESS")
        db.add(regular_org)
        await db.flush()
        regular_user = User(email="regular@client.test", password_hash=get_password_hash("Secret123!"), full_name="Regular Member", is_active=True, is_super_admin=False)
        db.add(regular_user)
        await db.flush()
        reg_member = OrganizationMember(organization_id=regular_org.id, user_id=regular_user.id, role="LEGAL_REVIEWER")
        db.add(reg_member)
        await db.commit()

        reg_user_id = regular_user.id
        reg_org_id = regular_org.id

    reg_token = create_access_token(subject=reg_user_id, org_id=reg_org_id, role="LEGAL_REVIEWER")
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Unauthenticated calls -> 401
        res_unauth1 = await ac.get("/api/v1/organizations/data-management/summary")
        assert res_unauth1.status_code == 401

        res_unauth2 = await ac.post("/api/v1/platform/data-management/demo-workspace/reset", json={"confirmation": "RESET DEMO"})
        assert res_unauth2.status_code == 401

        # Regular user trying to execute demo reset -> 403 Forbidden
        res_forbidden = await ac.post(
            "/api/v1/platform/data-management/demo-workspace/reset",
            headers={"Authorization": f"Bearer {reg_token}"},
            json={"confirmation": "RESET DEMO"}
        )
        assert res_forbidden.status_code == 403

